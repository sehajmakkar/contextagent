import AppKit
import SwiftUI

@main
enum Main {
    static func main() {
        // `ContextAgent --dump <bundle-id> [--out file]`: read one app's window once, print JSON, exit.
        // Launch it with `make dump` (via `open`), so it runs under the app's own Accessibility grant.
        if let i = CommandLine.arguments.firstIndex(of: "--dump") {
            DumpCommand.run(arguments: Array(CommandLine.arguments[(i + 1)...]))
        } else if let i = CommandLine.arguments.firstIndex(of: "--events") {
            // `--events <bundle-id> <seconds> --out file`: which change notifications does this app really send?
            MainActor.assumeIsolated { EventsCommand.run(arguments: Array(CommandLine.arguments[(i + 1)...])) }
        } else {
            ContextAgentApp.main()
        }
    }
}

struct ContextAgentApp: App {
    @State private var model: AppModel

    init() {
        let model = AppModel()
        model.start()
        _model = State(initialValue: model)
    }

    var body: some Scene {
        MenuBarExtra {
            MenuView(model: model)
        } label: {
            Image(systemName: model.menuBarSymbol)
        }
        .menuBarExtraStyle(.window)
    }
}

enum DumpCommand {
    static func run(arguments: [String]) {
        guard let bundleID = arguments.first else { finish(["error": "usage: --dump <bundle-id> [--out file]"]) }
        let out = arguments.firstIndex(of: "--out").flatMap { arguments.indices.contains($0 + 1) ? arguments[$0 + 1] : nil }
        guard AXPermission.isTrusted else {
            finish(["error": "Accessibility permission not granted to this app"], to: out)
        }
        guard let app = NSRunningApplication.runningApplications(withBundleIdentifier: bundleID).first else {
            finish(["error": "\(bundleID) is not running"], to: out)
        }
        AXUIElementSetMessagingTimeout(AXUIElementCreateSystemWide(), 0.5)
        let reader = WindowTextReader()
        guard let s = reader.read(pid: app.processIdentifier, appName: app.localizedName ?? bundleID, bundleID: bundleID) else {
            finish(["error": "no focused or main window"], to: out)
        }
        finish(["app": s.appName, "bundle_id": s.bundleID, "window_title": s.windowTitle, "url": s.url ?? NSNull(),
                "chars": s.text.count, "nodes_visited": s.nodesVisited, "truncated": s.truncated, "clipped_to_visible": s.clippedToVisible, "offscreen_skipped": s.offscreenSkipped,
                "elapsed_ms": s.elapsedMs, "roles": roleHistogram(pid: app.processIdentifier), "text": s.text], to: out)
    }

    /// "AXGroup/AXLandmarkNavigation": 3, …: what the window's tree is made of. A learning and debugging aid.
    private static func roleHistogram(pid: pid_t, limit: Int = 6_000) -> [String: Int] {
        guard let window = AXElement.application(pid: pid).element(AX.focusedWindow) else { return [:] }
        var counts: [String: Int] = [:]
        var stack = [window]
        var visited = 0
        while let element = stack.popLast(), visited < limit {
            visited += 1
            let a = element.attributes([AX.role, AX.subrole, AX.children])
            let role = a[AX.role] as? String ?? "?"
            let key = (a[AX.subrole] as? String).map { "\(role)/\($0)" } ?? role
            counts[key, default: 0] += 1
            stack += (a[AX.children] as? [AXUIElement] ?? []).map(AXElement.init)
        }
        return counts
    }

    private static func finish(_ object: [String: Any], to path: String? = nil) -> Never {
        let data = (try? JSONSerialization.data(withJSONObject: object, options: [.prettyPrinted, .sortedKeys])) ?? Data()
        if let path {
            FileManager.default.createFile(atPath: path, contents: data)
        } else {
            FileHandle.standardOutput.write(data)
        }
        exit(object["error"] == nil ? 0 : 1)
    }
}

@MainActor
enum EventsCommand {
    static func run(arguments: [String]) {
        let out = arguments.firstIndex(of: "--out").flatMap { arguments.indices.contains($0 + 1) ? arguments[$0 + 1] : nil }
        guard let bundleID = arguments.first,
              let app = NSRunningApplication.runningApplications(withBundleIdentifier: bundleID).first else {
            write(["error": "usage: --events <running bundle-id> <seconds> --out file"], to: out)
            exit(1)
        }
        let seconds = arguments.count > 1 ? Double(arguments[1]) ?? 10 : 10
        var counts: [String: Int] = [:]
        let source = AXEventSource { counts[$0, default: 0] += 1 }
        source.observe(pid: app.processIdentifier)
        let registered = source.registered
        RunLoop.main.run(until: Date().addingTimeInterval(seconds))  // callbacks arrive on this run loop
        write(["app": bundleID, "seconds": seconds, "registered": registered,
               "of": AXEventSource.notifications.count, "counts": counts], to: out)
        exit(0)
    }

    private static func write(_ object: [String: Any], to path: String?) {
        let data = (try? JSONSerialization.data(withJSONObject: object, options: [.prettyPrinted, .sortedKeys])) ?? Data()
        if let path { FileManager.default.createFile(atPath: path, contents: data) } else { FileHandle.standardOutput.write(data) }
    }
}
