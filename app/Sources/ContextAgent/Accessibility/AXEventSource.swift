import ApplicationServices

/// Subscribes to one app's accessibility notifications ("something changed") so we read when the
/// screen changes instead of guessing with a timer.
///
/// AXObserver predates Swift concurrency: callbacks arrive through a run-loop source, and the callback
/// is a C function pointer that can't capture Swift context, so `self` travels as an opaque pointer.
@MainActor
final class AXEventSource {
    /// Registered on the application element, these cover changes anywhere in the app.
    static let notifications = [
        "AXValueChanged",             // text edited, a field updated
        "AXFocusedUIElementChanged",  // focus moved to another element
        "AXFocusedWindowChanged",     // another window of the same app
        "AXTitleChanged",             // e.g. Gmail opened a different email
        "AXSelectedChildrenChanged",  // a different row selected in a list
        "AXRowCountChanged",          // rows added, e.g. a new chat message
        "AXLiveRegionChanged",        // web content announced an update (chat apps)
        "AXLayoutChanged",            // content moved or appeared
    ]

    private(set) var pid: pid_t = 0
    private(set) var registered = 0
    private var observer: AXObserver?
    private let onEvent: (String) -> Void

    init(onEvent: @escaping (String) -> Void) {
        self.onEvent = onEvent
    }

    func observe(pid: pid_t) {
        // Already fully registered for this app? Nothing to do. Partial (app still launching)? Retry.
        guard pid != self.pid || registered < Self.notifications.count else { return }
        stop()
        var created: AXObserver?
        guard AXObserverCreate(pid, axCallback, &created) == .success, let created else { return }
        let app = AXUIElementCreateApplication(pid)
        let refcon = Unmanaged.passUnretained(self).toOpaque()
        registered = Self.notifications.reduce(0) { count, name in
            count + (AXObserverAddNotification(created, app, name as CFString, refcon) == .success ? 1 : 0)
        }
        CFRunLoopAddSource(CFRunLoopGetMain(), AXObserverGetRunLoopSource(created), .defaultMode)
        observer = created
        self.pid = pid
    }

    func stop() {
        if let observer {
            CFRunLoopRemoveSource(CFRunLoopGetMain(), AXObserverGetRunLoopSource(observer), .defaultMode)
        }
        observer = nil
        pid = 0
        registered = 0
    }

    fileprivate func deliver(_ name: String) {
        onEvent(name)
    }
}

/// Runs on the main run loop (we added the source there), so hopping onto the main actor is safe.
private let axCallback: AXObserverCallback = { _, _, notification, refcon in
    guard let refcon else { return }
    let source = Unmanaged<AXEventSource>.fromOpaque(refcon).takeUnretainedValue()
    let name = notification as String
    MainActor.assumeIsolated { source.deliver(name) }
}
