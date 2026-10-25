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
    static let numberOfCharacters = "AXNumberOfCharacters"
    static let position = "AXPosition"
    static let size = "AXSize"
    static let visibleCharacterRange = "AXVisibleCharacterRange"
    static let stringForRange = "AXStringForRange"

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

    /// This element's on-screen rectangle (global coordinates), from AXPosition + AXSize.
    var frame: CGRect? {
        let a = attributes([AX.position, AX.size])
        return Self.frame(position: a[AX.position], size: a[AX.size])
    }

    static func frame(position: CFTypeRef?, size: CFTypeRef?) -> CGRect? {
        guard let position, let size, CFGetTypeID(position) == AXValueGetTypeID(),
              CFGetTypeID(size) == AXValueGetTypeID() else { return nil }
        var origin = CGPoint.zero
        var extent = CGSize.zero
        guard AXValueGetValue(position as! AXValue, .cgPoint, &origin),
              AXValueGetValue(size as! AXValue, .cgSize, &extent) else { return nil }
        return CGRect(origin: origin, size: extent)
    }

    /// A CFRange-valued attribute, e.g. AXVisibleCharacterRange (which characters are on screen).
    func range(_ name: String) -> CFRange? {
        guard let value = attribute(name), CFGetTypeID(value) == AXValueGetTypeID() else { return nil }
        var range = CFRange()
        return AXValueGetValue(value as! AXValue, .cfRange, &range) ? range : nil
    }

    /// A parameterized attribute: a query with an argument, e.g. AXStringForRange(range) → the text in it.
    func parameterized(_ name: String, _ parameter: CFTypeRef) -> CFTypeRef? {
        var value: CFTypeRef?
        guard AXUIElementCopyParameterizedAttributeValue(ref, name as CFString, parameter, &value) == .success else {
            return nil
        }
        return value
    }

    @discardableResult
    func set(_ name: String, _ value: CFTypeRef) -> AXError {
        AXUIElementSetAttributeValue(ref, name as CFString, value)
    }

    private static func isError(_ value: CFTypeRef) -> Bool {
        CFGetTypeID(value) == AXValueGetTypeID() && AXValueGetType(value as! AXValue) == .axError
    }
}
