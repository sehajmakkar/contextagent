import AppKit
import ApplicationServices
import Observation

/// App state and the capture loop: every 5s and on each app switch, read → decide → send.
@MainActor
@Observable
final class AppModel {
    struct AppRef: Equatable {
        let name: String
        let bundleID: String
    }

    struct Event {
        let at: Date
        let app: String
        let title: String
        let chars: Int
        let elapsedMs: Int
        let outcome: String
    }

    var isTrusted = AXPermission.isTrusted
    var isPaused = UserDefaults.standard.bool(forKey: "paused") {
        didSet { UserDefaults.standard.set(isPaused, forKey: "paused") }
    }
    var lastEvent: Event?
    var lastApp: AppRef?
    var brainStatus: BrainClient.Status?
    var brainError: String?
    private(set) var userExcluded = Set(UserDefaults.standard.stringArray(forKey: "excluded") ?? [])

    private var policy = CapturePolicy()
    private let reader = WindowTextReader()
    private let brain = BrainClient()
    private var isReading = false
    private var started = false
    private var switchObserver: NSObjectProtocol?

    var menuBarSymbol: String {
        if !isTrusted { return "eye.trianglebadge.exclamationmark" }
        if isPaused { return "eye.slash" }
        return brainError == nil ? "eye" : "eye.circle"
    }

    func start() {
        guard !started else { return }
        started = true
        policy.userExcluded = userExcluded
        // If a target app hangs, give up on it after 0.5s instead of freezing our capture loop.
        AXUIElementSetMessagingTimeout(AXUIElementCreateSystemWide(), 0.5)

        switchObserver = NSWorkspace.shared.notificationCenter.addObserver(
            forName: NSWorkspace.didActivateApplicationNotification, object: nil, queue: .main
        ) { [weak self] _ in
            MainActor.assumeIsolated { self?.captureSoon() }
        }
        Task {
            while true {
                await captureNow()
                try? await Task.sleep(for: .seconds(5))
            }
        }
        Task {
            while true {
                await refreshStatus()
                try? await Task.sleep(for: .seconds(10))
            }
        }
    }

    /// After an app switch, give the new window a moment to draw before reading it.
    func captureSoon() {
        Task {
            try? await Task.sleep(for: .seconds(1))
            await captureNow()
        }
    }

    func captureNow() async {
        isTrusted = AXPermission.isTrusted
        guard isTrusted, !isPaused, !isReading else { return }
        guard let app = NSWorkspace.shared.frontmostApplication, let bundleID = app.bundleIdentifier,
              bundleID != Bundle.main.bundleIdentifier else { return }
        let name = app.localizedName ?? bundleID
        lastApp = AppRef(name: name, bundleID: bundleID)

        // Excluded apps are never read, not just never sent.
        guard policy.allows(bundleID: bundleID) else {
            lastEvent = Event(at: .now, app: name, title: "", chars: 0, elapsedMs: 0, outcome: "excluded, not read")
            return
        }

        isReading = true
        defer { isReading = false }
        let pid = app.processIdentifier
        let reader = self.reader
        // AX calls are blocking IPC into the other app, so they run off the main thread.
        let snapshot = await Task.detached(priority: .utility) {
            reader.read(pid: pid, appName: name, bundleID: bundleID)
        }.value
        guard let snapshot else {
            lastEvent = Event(at: .now, app: name, title: "", chars: 0, elapsedMs: 0, outcome: "no focused window")
            return
        }

        switch policy.decide(snapshot) {
        case let .skip(reason):
            record(snapshot, reason.rawValue)
        case .send:
            do {
                let response = try await brain.post(snapshot)
                let redacted = response.redactions.values.reduce(0, +)
                record(snapshot, response.status + (redacted > 0 ? " · \(redacted) redacted" : ""))
                await refreshStatus()
            } catch {
                policy.sendFailed(snapshot)
                record(snapshot, "not sent: \(error.localizedDescription)")
            }
        }
    }

    func refreshStatus() async {
        do {
            brainStatus = try await brain.status()
            brainError = nil
        } catch {
            brainStatus = nil
            brainError = error.localizedDescription
        }
    }

    func requestPermission() {
        AXPermission.requestPrompt()
        AXPermission.openSettings()
    }

    func exclude(_ app: AppRef) {
        userExcluded.insert(app.bundleID)
        saveExclusions()
    }

    func clearExclusions() {
        userExcluded.removeAll()
        saveExclusions()
    }

    private func saveExclusions() {
        policy.userExcluded = userExcluded
        UserDefaults.standard.set(Array(userExcluded), forKey: "excluded")
    }

    private func record(_ s: WindowSnapshot, _ outcome: String) {
        lastEvent = Event(at: .now, app: s.appName, title: s.windowTitle, chars: s.text.count,
                          elapsedMs: s.elapsedMs, outcome: outcome)
    }
}
