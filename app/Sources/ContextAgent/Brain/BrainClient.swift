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
            case let .http(code, body): "Brain returned \(code): \(body.prefix(120))"
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
        let tier: String
        let liveDetectionAllowed: Bool
        let autoDetectRunning: Bool
        let captured: Int
        let pending: Int
        let heldBack: Int
        let openLoops: Int
        let lastError: String?
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

    private func authorized(_ path: String) throws -> URLRequest {
        guard let token = try? String(contentsOf: Self.tokenURL, encoding: .utf8) else { throw BrainError.noToken }
        var request = URLRequest(url: baseURL.appending(path: path), timeoutInterval: 5)
        request.setValue(token.trimmingCharacters(in: .whitespacesAndNewlines), forHTTPHeaderField: "X-Brain-Token")
        return request
    }

    private func send<T: Decodable>(_ request: URLRequest) async throws -> T {
        let (data, response) = try await URLSession.shared.data(for: request)
        let code = (response as? HTTPURLResponse)?.statusCode ?? 0
        guard code == 200 else { throw BrainError.http(code, String(decoding: data, as: UTF8.self)) }
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return try decoder.decode(T.self, from: data)
    }
}
