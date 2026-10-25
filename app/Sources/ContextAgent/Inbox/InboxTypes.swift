import Foundation

// Shapes the brain returns (decoded with .convertFromSnakeCase). All text in them is untrusted:
// render it with Text(verbatim:), never as Markdown or attributed strings.

struct Loop: Decodable, Sendable, Identifiable, Equatable {
    let id: Int
    let title: String
    let direction: String            // i_owe | they_owe | self
    let counterparty: String
    let deliverable: String
    let note: String?
    let dueDate: String?             // YYYY-MM-DD
    let state: String                // open | acting | awaiting_approval | closed | dismissed
    let closedReason: String?        // user | inferred | agent
    let sourceApp: String?
    let bundleId: String?
    let windowTitle: String?
    let quote: String?
    let seen: Int
    let updatedAt: String
    let lastActionId: Int?
    let lastActionStatus: String?
    let proofUrl: String?
}

struct Memory: Decodable, Sendable, Identifiable, Equatable {
    let id: Int
    let kind: String
    let text: String
    let appName: String
    let bundleId: String
    let happenedAt: String
}

struct Draft: Decodable, Sendable, Equatable {
    let draftId: String
    let threadId: String?
    let kind: String?              // reply | new (no thread: the promise was made outside email)
    let to: [String]
    let subject: String
    let body: String
    let draftHash: String

    var isNewEmail: Bool { kind == "new" }
}

struct AgentAction: Decodable, Sendable, Equatable {
    struct Step: Decodable, Sendable, Equatable {
        let tool: String
        let status: String
    }

    let id: Int
    let loopId: Int?
    let status: String               // running | awaiting_approval | sending | sent | rejected | failed | cannot_close …
    let outcome: String?
    let summary: String?
    let draft: Draft?
    let missingInfo: [String]
    let steps: [Step]
}

enum AgentEvent: Sendable, Equatable {
    case thinking(turn: Int)
    case step(tool: String, status: String, label: String)
    case done(AgentAction)
    case failed(String)
}
