import Foundation

/// Talks to the Python brain on 127.0.0.1 (ADR-004). The app never opens the database itself.
struct BrainClient: Sendable {
    var baseURL = URL(string: "http://127.0.0.1:8765")!

    /// Written by `brain serve` with 0600 permissions. Only processes running as you can read it.
    static let tokenURL = FileManager.default.homeDirectoryForCurrentUser
        .appending(path: "Library/Application Support/ContextAgent/brain.token")

    enum BrainError: LocalizedError {
        case noToken
        case http(Int, String)

        var errorDescription: String? {
            switch self {
            case .noToken: "No token yet: start the brain with `make brain`"
            case let .http(code, body): code == 0 ? "Brain not reachable" : "\(body.prefix(160)) (\(code))"
            }
        }
    }

    struct Observation: Encodable {
        let capturedAt: String
        let appName: String
        let bundleId: String
        let windowTitle: String
        let url: String?
        let text: String
        let trigger: String

        enum CodingKeys: String, CodingKey {
            case capturedAt = "captured_at", appName = "app_name", bundleId = "bundle_id"
            case windowTitle = "window_title", url, text, trigger
        }
    }

    struct IngestResponse: Decodable, Sendable {
        let status: String
        let observationId: Int?
        let redactions: [String: Int]
    }

    struct Status: Decodable, Sendable {
        let autoDetectRunning: Bool
        let captured: Int
        let pending: Int
        let openLoops: Int
        let lastError: String?
        let agentReady: Bool
        let agentDetail: String
    }

    func post(_ snapshot: WindowSnapshot, trigger: String, capturedAt: Date = .now) async throws -> IngestResponse {
        let body = Observation(capturedAt: Self.localTimestamp(capturedAt), appName: snapshot.appName,
                               bundleId: snapshot.bundleID, windowTitle: snapshot.windowTitle,
                               url: snapshot.url, text: snapshot.text, trigger: trigger)
        var request = try authorized("observations")
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(body)
        return try await send(request)
    }

    func status() async throws -> Status {
        try await send(try authorized("status"))
    }

    /// Local time *with* its UTC offset, e.g. 2026-10-25T11:00:00+05:30. The brain resolves
    /// "by Wednesday" against this, so a bare UTC time could shift the weekday near midnight.
    static func localTimestamp(_ date: Date) -> String {
        let formatter = ISO8601DateFormatter()
        formatter.timeZone = .current
        formatter.formatOptions = [.withInternetDateTime]
        return formatter.string(from: date)
    }

    // MARK: - Inbox (Phase 6)

    func loops(state: String = "open") async throws -> [Loop] {
        var request = try authorized("loops")
        request.url = request.url?.appending(queryItems: [URLQueryItem(name: "state", value: state)])
        return try await send(request)
    }

    func memories(limit: Int = 20) async throws -> [Memory] {
        var request = try authorized("memories")
        request.url = request.url?.appending(queryItems: [URLQueryItem(name: "limit", value: String(limit))])
        return try await send(request)
    }

    func action(_ id: Int) async throws -> AgentAction {
        try await send(try authorized("actions/\(id)"))
    }

    func transition(loopID: Int, to state: String, reason: String) async throws {
        let _: Loop = try await send(try json(post: "loops/\(loopID)/transition", ["to": state, "reason": reason]))
    }

    func approve(actionID: Int, draftHash: String, editedBody: String?, to: [String]?) async throws -> AgentAction {
        struct Body: Encodable {
            let draft_hash: String
            let body: String?
            let to: [String]?
        }
        var request = try authorized("actions/\(actionID)/approve")
        request.httpMethod = "POST"
        request.timeoutInterval = 60
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(Body(draft_hash: draftHash, body: editedBody, to: to))
        return try await send(request)
    }

    func reject(actionID: Int, reason: String) async throws -> AgentAction {
        try await send(try json(post: "actions/\(actionID)/reject", ["reason": reason]))
    }

    /// You switched away from this window: the brain processes the visit now instead of in 5 minutes (ADR-051).
    func endVisit(bundleID: String, windowTitle: String) async throws {
        let _: [String: Int?] = try await send(try json(post: "visits/end", ["bundle_id": bundleID, "window_title": windowTitle]))
    }

    func deleteAllData() async throws {
        let _: [String: [String: Int]] = try await send(try json(post: "data/delete", ["confirm": "delete everything"]))
    }

    /// "Close it for me", streamed: Server-Sent Events, one `data: {json}` line per agent step (ADR-049).
    func closeStream(loopID: Int) -> AsyncThrowingStream<AgentEvent, Error> {
        AsyncThrowingStream { continuation in
            let task = Task {
                do {
                    var request = try authorized("loops/\(loopID)/close/stream")
                    request.httpMethod = "POST"
                    request.timeoutInterval = 180  // an agent run takes seconds; give slow networks room
                    let (bytes, response) = try await URLSession.shared.bytes(for: request)
                    let code = (response as? HTTPURLResponse)?.statusCode ?? 0
                    if code != 200 {
                        var detail = ""
                        for try await line in bytes.lines { detail += line }
                        throw BrainError.http(code, SSE.detail(fromErrorBody: detail))
                    }
                    for try await line in bytes.lines {
                        if let event = SSE.event(from: line) { continuation.yield(event) }
                    }
                    continuation.finish()
                } catch {
                    continuation.finish(throwing: error)
                }
            }
            continuation.onTermination = { _ in task.cancel() }
        }
    }

    private func json(post path: String, _ body: [String: String], timeout: TimeInterval = 10) throws -> URLRequest {
        var request = try authorized(path)
        request.httpMethod = "POST"
        request.timeoutInterval = timeout
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(body)
        return request
    }

    private func authorized(_ path: String) throws -> URLRequest {
        guard let token = try? String(contentsOf: Self.tokenURL, encoding: .utf8) else { throw BrainError.noToken }
        var request = URLRequest(url: baseURL.appending(path: path), timeoutInterval: 5)
        request.setValue(token.trimmingCharacters(in: .whitespacesAndNewlines), forHTTPHeaderField: "X-Brain-Token")
        return request
    }

    private func send<T: Decodable>(_ request: URLRequest) async throws -> T {
        let (data, response) = try await URLSession.shared.data(for: request)
        let code = (response as? HTTPURLResponse)?.statusCode ?? 0
        guard code == 200 else {
            throw BrainError.http(code, SSE.detail(fromErrorBody: String(decoding: data, as: UTF8.self)))
        }
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return try decoder.decode(T.self, from: data)
    }
}
