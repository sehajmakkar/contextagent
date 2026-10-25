import Foundation

/// Server-Sent Events: the brain streams `data: {json}` lines while the agent works (ADR-049).
enum SSE {
    private struct Raw: Decodable {
        let type: String
        let tool: String?
        let status: String?
        let label: String?
        let turn: Int?
        let action: AgentAction?
        let detail: String?
    }

    static func event(from line: String) -> AgentEvent? {
        guard line.hasPrefix("data: "), let data = line.dropFirst(6).data(using: .utf8) else { return nil }
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        guard let raw = try? decoder.decode(Raw.self, from: data) else { return nil }
        switch raw.type {
        case "thinking": return .thinking(turn: raw.turn ?? 0)
        case "step": return .step(tool: raw.tool ?? "", status: raw.status ?? "", label: raw.label ?? raw.tool ?? "")
        case "done": return raw.action.map(AgentEvent.done)
        case "error": return .failed(raw.detail ?? "unknown error")
        default: return nil
        }
    }

    /// FastAPI errors look like {"detail": "..."}; show just the message.
    static func detail(fromErrorBody body: String) -> String {
        struct ErrorBody: Decodable { let detail: String }
        if let data = body.data(using: .utf8), let parsed = try? JSONDecoder().decode(ErrorBody.self, from: data) {
            return parsed.detail
        }
        return body
    }
}

enum InboxLogic {
    /// `[[...]]` slots the agent left for things only you know. Approve stays disabled until they're filled,
    /// so a half-finished draft can't be sent by accident (ADR-050).
    static func placeholders(in body: String) -> [String] {
        body.matches(of: /\[\[(.+?)\]\]/).map { String($0.output.1) }
    }

    /// "a@x.com, b@y.com" → ["a@x.com", "b@y.com"]; nil if any address is malformed.
    static func recipients(_ field: String) -> [String]? {
        let parts = field.split(whereSeparator: { $0 == "," || $0 == ";" || $0.isWhitespace })
            .map { $0.lowercased() }.filter { !$0.isEmpty }
        let valid = parts.allSatisfy { $0.wholeMatch(of: /[^@\s<>,;]+@[^@\s<>,;]+\.[^@\s<>,;]+/) != nil }
        return valid ? parts : nil
    }

    enum DueGroup: String, CaseIterable {
        case overdue = "Overdue"
        case today = "Today"
        case soon = "Next 7 days"
        case later = "Later"
        case none = "No deadline"
    }

    static func dueGroup(_ due: String?, today: Date = .now, calendar: Calendar = .current) -> DueGroup {
        guard let due, let date = parseDay(due) else { return .none }
        let start = calendar.startOfDay(for: today)
        let days = calendar.dateComponents([.day], from: start, to: calendar.startOfDay(for: date)).day ?? 0
        switch days {
        case ..<0: return .overdue
        case 0: return .today
        case 1...7: return .soon
        default: return .later
        }
    }

    static func parseDay(_ value: String) -> Date? {
        let formatter = DateFormatter()
        formatter.calendar = Calendar(identifier: .gregorian)
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter.date(from: value)
    }

    /// The app chips above the list (All · Google Chrome · WhatsApp …), most loops first.
    static func appFilters(_ loops: [Loop]) -> [String] {
        let counts = Dictionary(grouping: loops.compactMap(\.sourceApp), by: { $0 }).mapValues(\.count)
        return counts.sorted { $0.value == $1.value ? $0.key < $1.key : $0.value > $1.value }.map(\.key)
    }
}
