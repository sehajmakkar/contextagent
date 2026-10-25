import Foundation

/// Decides which snapshots get sent to the brain. Pure logic, no macOS calls, so it's unit-tested.
struct CapturePolicy {
    enum Decision: Equatable {
        case send
        case skip(Reason)
    }

    enum Reason: String {
        case tooShort = "too little text"
        case unchanged = "unchanged"
        case settling = "waiting for the screen to settle"
    }

    /// Never read these at all: secrets live here (ADR-014). Checked before any AX call.
    static let alwaysExcluded: Set<String> = [
        "com.1password.1password", "com.agilebits.onepassword7", "com.bitwarden.desktop",
        "com.lastpass.LastPass", "com.apple.keychainaccess", "com.apple.Passwords",
        "com.apple.systempreferences", "com.apple.loginwindow", "com.apple.ScreenSaver.Engine",
    ]

    var minChars = 40
    var userExcluded: Set<String> = []

    private var lastSent: [String: String] = [:]   // window → fingerprint of what we last sent
    private var pending: [String: String] = [:]    // window → fingerprint seen once, not yet stable

    func allows(bundleID: String) -> Bool {
        !Self.alwaysExcluded.contains(bundleID) && !userExcluded.contains(bundleID)
    }

    /// Why we're reading. It decides how sure we need to be that the screen is stable.
    enum Trigger: String {
        /// After change notifications went quiet: the quiet period already proves stability.
        case settled
        /// You're switching away: last chance to capture this window, so send whatever changed.
        case leaving
        /// Backup timer for apps with poor notifications: require the same text on two reads in a row.
        case poll
    }

    /// Send only text that is new *and* stable. That skips half-typed sentences and pages still loading.
    mutating func decide(_ snapshot: WindowSnapshot, trigger: Trigger = .poll) -> Decision {
        guard snapshot.text.count >= minChars else { return .skip(.tooShort) }
        let key = Self.windowKey(snapshot)
        let print = Self.fingerprint(snapshot.text)
        if lastSent[key] == print { return .skip(.unchanged) }
        if trigger == .poll, pending[key] != print {
            pending[key] = print
            return .skip(.settling)
        }
        pending[key] = nil
        lastSent[key] = print
        return .send
    }

    /// The brain didn't take it (offline, error): resend on the next read. It already proved stable,
    /// so it goes back to `pending` instead of settling again.
    mutating func sendFailed(_ snapshot: WindowSnapshot) {
        let key = Self.windowKey(snapshot)
        lastSent[key] = nil
        pending[key] = Self.fingerprint(snapshot.text)
    }

    static func windowKey(_ s: WindowSnapshot) -> String { s.bundleID + "\u{0}" + s.windowTitle }

    /// Digits masked, so a ticking clock or unread badge doesn't count as a change (same rule as the brain).
    static func fingerprint(_ text: String) -> String {
        text.replacing(/\d+/, with: "#")
    }
}
