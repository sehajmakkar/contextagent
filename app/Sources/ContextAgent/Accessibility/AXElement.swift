import ApplicationServices

/// Raw attribute and role names, spelled exactly as Accessibility Inspector shows them.
enum AX {
    static let role = "AXRole"
    static let subrole = "AXSubrole"
    static let title = "AXTitle"
    static let value = "AXValue"
    static let description = "AXDescription"
    static let children = "AXChildren"
    static let focusedWindow = "AXFocusedWindow"
    static let mainWindow = "AXMainWindow"
    static let url = "AXURL"
    /// Chromium and Electron only build their accessibility tree when an assistive app asks for it.
    static let manualAccessibility = "AXManualAccessibility"

    static let webArea = "AXWebArea"
    static let secureTextField = "AXSecureTextField"
}

/// A thin wrapper over `AXUIElement`, a handle to one UI element in another app.
/// Every read is an IPC round trip to that app, so we batch attributes where we can.
struct AXElement {
    let ref: AXUIElement

    static func application(pid: pid_t) -> AXElement {
        AXElement(ref: AXUIElementCreateApplication(pid))
    }

    func attribute(_ name: String) -> CFTypeRef? {
        var value: CFTypeRef?
        guard AXUIElementCopyAttributeValue(ref, name as CFString, &value) == .success else { return nil }
        return value
    }

    func string(_ name: String) -> String? {
        attribute(name) as? String
    }

    func element(_ name: String) -> AXElement? {
        guard let value = attribute(name), CFGetTypeID(value) == AXUIElementGetTypeID() else { return nil }
        return AXElement(ref: value as! AXUIElement)
    }

    /// Several attributes in one IPC call. Missing ones come back as an `AXValue` of type `.axError`; we drop them.
    func attributes(_ names: [String]) -> [String: CFTypeRef] {
        var values: CFArray?
        guard AXUIElementCopyMultipleAttributeValues(ref, names as CFArray, [], &values) == .success,
              let array = values as? [CFTypeRef] else { return [:] }
        var result: [String: CFTypeRef] = [:]
        for (name, value) in zip(names, array) where !Self.isError(value) {
            result[name] = value
        }
        return result
    }

    @discardableResult
    func set(_ name: String, _ value: CFTypeRef) -> AXError {
        AXUIElementSetAttributeValue(ref, name as CFString, value)
    }

    private static func isError(_ value: CFTypeRef) -> Bool {
        CFGetTypeID(value) == AXValueGetTypeID() && AXValueGetType(value as! AXValue) == .axError
    }
}
