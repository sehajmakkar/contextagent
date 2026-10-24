import AppKit
import ApplicationServices

/// The Accessibility permission (a TCC grant) lets this app read other apps' UI.
/// macOS ties the grant to the app's code signature, so an unsigned rebuild loses it.
enum AXPermission {
    static var isTrusted: Bool { AXIsProcessTrusted() }

    /// Shows the system "would like to control this computer using accessibility features" prompt.
    static func requestPrompt() {
        // The string value of kAXTrustedCheckOptionPrompt; that global is not concurrency-safe in Swift 6.
        let options = ["AXTrustedCheckOptionPrompt": true] as CFDictionary
        _ = AXIsProcessTrustedWithOptions(options)
    }

    static func openSettings() {
        let url = URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility")!
        NSWorkspace.shared.open(url)
    }
}
