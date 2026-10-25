import AppKit
import ApplicationServices
import Observation
import os

/// `log stream --predicate 'subsystem == "com.sehajpreet.contextagent"'` — IDs, triggers and counts only, never text.
private let log = Logger(subsystem: "com.sehajpreet.contextagent", category: "capture")

/// App state and the capture loop (ADR-032):
/// - change notifications from the frontmost app → one read after the burst settles;
/// - switching away from an app → read it one last time and send what's new;
/// - a slow backup poll for apps that send few notifications.
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
        let trigger: String
        let outcome: String
    }

    static let backupPollInterval: Duration = .seconds(30)

    var isTrusted = AXPermission.isTrusted
    var isPaused = UserDefaults.standard.bool(forKey: "paused") {
        didSet { UserDefaults.standard.set(isPaused, forKey: "paused") }
    }
    var lastEvent: Event?
    var lastApp: AppRef?
    var brainStatus: BrainClient.Status?
    var brainError: String?
    /// Notifications received from the observed app since launch (a learning and debugging aid).
    private(set) var notificationCount = 0
    private(set) var userExcluded = Set(UserDefaults.standard.stringArray(forKey: "excluded") ?? [])

    private var policy = CapturePolicy()
    private var coalescer = EventCoalescer()
    private let reader = WindowTextReader()
    private let brain = BrainClient()
    private var reading: Set<pid_t> = []
    /// A just-launched app may not have a window yet when the first read fires.
    private var noWindowRetries = 0
    private var scheduledRead: Task<Void, Never>?
    private var started = false
    private var workspaceObservers: [NSObjectProtocol] = []
    @ObservationIgnored private lazy var events = AXEventSource { [weak self] _ in self?.changeNoticed() }

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

        let center = NSWorkspace.shared.notificationCenter
        workspaceObservers = [
            center.addObserver(forName: NSWorkspace.didActivateApplicationNotification, object: nil, queue: .main) {
                [weak self] note in
                let app = note.userInfo?[NSWorkspace.applicationUserInfoKey] as? NSRunningApplication
                MainActor.assumeIsolated { self?.appActivated(app) }
            },
            center.addObserver(forName: NSWorkspace.didDeactivateApplicationNotification, object: nil, queue: .main) {
                [weak self] note in
                let app = note.userInfo?[NSWorkspace.applicationUserInfoKey] as? NSRunningApplication
                MainActor.assumeIsolated { self?.appDeactivated(app) }
            },
        ]
        appActivated(NSWorkspace.shared.frontmostApplication)

        Task {
            while true {
                try? await Task.sleep(for: Self.backupPollInterval)
                if let app = NSWorkspace.shared.frontmostApplication { await capture(app, trigger: .poll) }
            }
        }
        Task {
            while true {
                await refreshStatus()
                try? await Task.sleep(for: .seconds(10))
            }
        }
    }

    // MARK: - Triggers

    private func appActivated(_ app: NSRunningApplication?) {
        isTrusted = AXPermission.isTrusted
        guard let app, isCapturable(app) else {
            events.stop()
            return
        }
        events.observe(pid: app.processIdentifier)
        log.info("activated \(app.bundleIdentifier ?? "?", privacy: .public) observing=\(self.events.registered)")
        changeNoticed()  // read the newly focused window once it has drawn
    }

    /// Flush on leave: the window you're leaving won't be seen again, so read it now.
    private func appDeactivated(_ app: NSRunningApplication?) {
        guard let app, isCapturable(app) else { return }
        log.info("deactivated \(app.bundleIdentifier ?? "?", privacy: .public) → leaving read")
        // Don't cancel the scheduled settled read: macOS delivers "deactivated" *after* the next app's
        // "activated", so that read already belongs to the new app.
        Task { await capture(app, trigger: .leaving) }
    }

    private func changeNoticed() {
        notificationCount += 1
        coalescer.record(.now)
        guard let fireAt = coalescer.fireAt else { return }
        scheduledRead?.cancel()
        scheduledRead = Task { [weak self] in
            try? await Task.sleep(for: .seconds(max(0, fireAt.timeIntervalSinceNow)))
            guard !Task.isCancelled, let self else { return }
            self.coalescer.reset()
            guard let app = NSWorkspace.shared.frontmostApplication else { return }
            // A launching app refuses notification registration until it's ready, so retry here.
            if self.isCapturable(app) { self.events.observe(pid: app.processIdentifier) }
            await self.capture(app, trigger: .settled)
        }
    }

    // MARK: - Capture

    private func isCapturable(_ app: NSRunningApplication) -> Bool {
        app.bundleIdentifier != nil && app.bundleIdentifier != Bundle.main.bundleIdentifier
    }

    func captureNow() async {
        if let app = NSWorkspace.shared.frontmostApplication { await capture(app, trigger: .settled) }
    }

    private func capture(_ app: NSRunningApplication, trigger: CapturePolicy.Trigger) async {
        isTrusted = AXPermission.isTrusted
        guard isTrusted, !isPaused, isCapturable(app), let bundleID = app.bundleIdentifier else { return }
        let pid = app.processIdentifier
        guard !reading.contains(pid) else {
            log.info("\(trigger.rawValue, privacy: .public) skipped: read already running for \(bundleID, privacy: .public)")
            return
        }
        let name = app.localizedName ?? bundleID
        if trigger != .leaving { lastApp = AppRef(name: name, bundleID: bundleID) }

        // Excluded apps are never read, not just never sent.
        guard policy.allows(bundleID: bundleID) else {
            lastEvent = Event(at: .now, app: name, title: "", chars: 0, elapsedMs: 0,
                              trigger: trigger.rawValue, outcome: "excluded, not read")
            return
        }

        reading.insert(pid)
        defer { reading.remove(pid) }
        let reader = self.reader
        // AX calls are blocking IPC into the other app, so they run off the main thread.
        let snapshot = await Task.detached(priority: .utility) {
            reader.read(pid: pid, appName: name, bundleID: bundleID)
        }.value
        guard let snapshot else {
            // Launch race: the app activated before its window existed, and its "window appeared"
            // notification may have fired before we were listening. Try again shortly, a few times.
            log.info("\(trigger.rawValue, privacy: .public) \(bundleID, privacy: .public): no window (retry \(self.noWindowRetries))")
            if trigger == .settled, noWindowRetries < 3 {
                noWindowRetries += 1
                changeNoticed()
            }
            return
        }
        noWindowRetries = 0

        let decision = policy.decide(snapshot, trigger: trigger)
        log.info("\(trigger.rawValue, privacy: .public) \(bundleID, privacy: .public) chars=\(snapshot.text.count) → \(String(describing: decision), privacy: .public)")
        switch decision {
        case let .skip(reason):
            record(snapshot, trigger, reason.rawValue)
        case .send:
            do {
                let response = try await brain.post(snapshot, trigger: trigger.rawValue)
                let redacted = response.redactions.values.reduce(0, +)
                record(snapshot, trigger, response.status + (redacted > 0 ? " · \(redacted) redacted" : ""))
                await refreshStatus()
            } catch {
                policy.sendFailed(snapshot)
                record(snapshot, trigger, "not sent: \(error.localizedDescription)")
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

    private func record(_ s: WindowSnapshot, _ trigger: CapturePolicy.Trigger, _ outcome: String) {
        lastEvent = Event(at: .now, app: s.appName, title: s.windowTitle, chars: s.text.count,
                          elapsedMs: s.elapsedMs, trigger: trigger.rawValue, outcome: outcome)
    }
}
