import ApplicationServices
import Foundation

struct WindowSnapshot: Sendable, Equatable {
    var appName: String
    var bundleID: String
    var windowTitle: String
    var url: String?
    var text: String
    var nodesVisited: Int
    var truncated: Bool
    var elapsedMs: Int
}

/// Reads the text of an app's focused window by walking its accessibility tree. No pixels, ever (ADR-005).
struct WindowTextReader: Sendable {
    var maxNodes = 5_000
    var maxDepth = 60
    var maxChars = 20_000

    /// Roles whose `AXValue` is the text a person reads or types.
    static let valueRoles: Set<String> = ["AXStaticText", "AXTextField", "AXTextArea", "AXComboBox"]
    /// Roles whose label (`AXTitle` / `AXDescription`) carries meaning: headings, links, buttons, tabs.
    static let labelRoles: Set<String> = ["AXHeading", "AXLink", "AXButton", "AXTab", "AXRadioButton",
                                          "AXCheckBox", "AXPopUpButton", "AXMenuButton", "AXCell"]
    /// Whole subtrees that are app chrome, not content.
    static let skipRoles: Set<String> = ["AXMenuBar", "AXToolbar", "AXScrollBar", "AXImage"]
    /// ARIA landmarks that a page marks as chrome: site header, nav menus, search bar, side panels, footer.
    /// We keep AXLandmarkMain and AXLandmarkRegion, where the content lives.
    static let skipSubroles: Set<String> = ["AXLandmarkBanner", "AXLandmarkNavigation", "AXLandmarkSearch",
                                            "AXLandmarkComplementary", "AXLandmarkContentInfo"]

    func read(pid: pid_t, appName: String, bundleID: String) -> WindowSnapshot? {
        let start = Date()
        let app = AXElement.application(pid: pid)
        // Harmless for native apps; makes Chrome, Slack and VS Code expose their web content.
        app.set(AX.manualAccessibility, true as CFTypeRef)

        guard let window = app.element(AX.focusedWindow) ?? app.element(AX.mainWindow) else { return nil }
        let title = window.string(AX.title) ?? ""

        // In a browser, read only the page (the AXWebArea), not tabs, toolbar and bookmarks.
        let webArea = findWebArea(in: window)
        let root = webArea ?? window
        let url = webArea.flatMap { ($0.attribute(AX.url) as? URL).map(Self.redactQuery) }

        var collector = TextCollector(maxChars: maxChars)
        var stack: [(AXElement, Int)] = [(root, 0)]
        var visited = 0
        while let (element, depth) = stack.popLast() {
            visited += 1
            if visited > maxNodes || collector.isFull { break }

            let basics = element.attributes([AX.role, AX.subrole, AX.children])
            let role = basics[AX.role] as? String ?? ""
            let subrole = basics[AX.subrole] as? String ?? ""
            // Password fields: skip the subtree and never request the value.
            if role == AX.secureTextField || subrole == AX.secureTextField { continue }
            if Self.skipRoles.contains(role) || Self.skipSubroles.contains(subrole) { continue }

            if Self.valueRoles.contains(role), let text = element.string(AX.value), !text.isEmpty {
                collector.add(text)
                // Rich-text editors (Gmail compose) also expose the same words as child spans. Don't read them twice.
                continue
            } else if Self.labelRoles.contains(role) {
                let labels = element.attributes([AX.title, AX.description])
                if let text = (labels[AX.title] as? String) ?? (labels[AX.description] as? String) {
                    collector.add(text)
                }
            }

            if depth < maxDepth, let children = basics[AX.children] as? [AXUIElement] {
                // Reverse so the stack pops children in reading order (top to bottom).
                stack.append(contentsOf: children.reversed().map { (AXElement(ref: $0), depth + 1) })
            }
        }

        return WindowSnapshot(
            appName: appName, bundleID: bundleID, windowTitle: title, url: url, text: collector.text,
            nodesVisited: visited, truncated: visited > maxNodes || collector.isFull,
            elapsedMs: Int(Date().timeIntervalSince(start) * 1000)
        )
    }

    /// Breadth-first, so we find the main page before any embedded frames.
    private func findWebArea(in window: AXElement, limit: Int = 2_000) -> AXElement? {
        var queue = [window]
        var index = 0
        while index < queue.count, index < limit {
            let element = queue[index]
            index += 1
            let attrs = element.attributes([AX.role, AX.children])
            if attrs[AX.role] as? String == AX.webArea { return element }
            if let children = attrs[AX.children] as? [AXUIElement] {
                queue.append(contentsOf: children.map(AXElement.init))
            }
        }
        return nil
    }

    /// Query strings often carry tokens (password resets, OAuth codes). Keep scheme, host, path, fragment.
    static func redactQuery(_ url: URL) -> String {
        guard var parts = URLComponents(url: url, resolvingAgainstBaseURL: false) else { return "" }
        parts.query = nil
        parts.user = nil
        parts.password = nil
        return parts.string ?? ""
    }
}

/// Builds the snapshot text: one line per UI element, whitespace collapsed, repeats dropped, size capped.
struct TextCollector {
    let maxChars: Int
    private(set) var lines: [String] = []
    private(set) var count = 0

    var isFull: Bool { count >= maxChars }
    var text: String { lines.joined(separator: "\n") }

    /// Invisible direction marks and zero-width spaces (WhatsApp prefixes most labels with U+200E).
    /// They cost tokens and make identical text compare as different.
    static let invisibles: Set<Character> = ["\u{200B}", "\u{200E}", "\u{200F}", "\u{202A}", "\u{202B}", "\u{202C}",
                                             "\u{202D}", "\u{202E}", "\u{2066}", "\u{2067}", "\u{2068}", "\u{2069}", "\u{FEFF}"]

    mutating func add(_ raw: String) {
        let visible = String(raw.filter { !Self.invisibles.contains($0) })
        for part in visible.split(whereSeparator: \.isNewline) {
            var line = part.split(whereSeparator: \.isWhitespace).joined(separator: " ")
            // A link and its label child often repeat the same text back to back.
            guard !line.isEmpty, line != lines.last, !isFull else { continue }
            // One value can be huge (a code editor exposes the whole file), so cut it to the budget left.
            line = String(line.prefix(maxChars - count))
            lines.append(line)
            count += line.count + 1
        }
    }
}
