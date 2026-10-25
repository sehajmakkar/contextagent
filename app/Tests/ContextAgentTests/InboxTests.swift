import Foundation
import Testing
@testable import ContextAgent

@Test func sseLinesBecomeAgentEvents() {
    #expect(SSE.event(from: #"data: {"type": "step", "tool": "mail_search", "status": "ok", "label": "Searching your mail"}"#)
            == .step(tool: "mail_search", status: "ok", label: "Searching your mail"))
    #expect(SSE.event(from: #"data: {"type": "error", "detail": "Gmail not connected"}"#) == .failed("Gmail not connected"))
    #expect(SSE.event(from: "") == nil)                  // the blank separator line between events
    #expect(SSE.event(from: ": keep-alive") == nil)      // SSE comment
    #expect(SSE.event(from: "data: not json") == nil)
}

@Test func doneEventCarriesTheDraftForReview() throws {
    let line = #"data: {"type": "done", "action": {"id": 7, "loop_id": 1, "status": "awaiting_approval", "outcome": "drafted", "summary": "ok", "missing_info": [], "steps": [{"tool": "create_draft", "status": "ok"}], "draft": {"draft_id": "d1", "thread_id": "t1", "to": ["priya@x.example"], "subject": "Re: Q3", "body": "Hi Priya", "draft_hash": "abc"}}}"#
    guard case let .done(action) = SSE.event(from: line) else { Issue.record("not a done event"); return }
    #expect(action.id == 7 && action.draft?.draftHash == "abc" && action.draft?.to == ["priya@x.example"])
}

@Test func placeholdersBlockApprove() {
    #expect(InboxLogic.placeholders(in: "Hi Karan, [[renew or not?]] Thanks") == ["renew or not?"])
    #expect(InboxLogic.placeholders(in: "Times: [[Tue]] or [[Wed]]") == ["Tue", "Wed"])
    #expect(InboxLogic.placeholders(in: "Hi Priya, 63.6% [link]").isEmpty)
}

@Test func dueDatesGroupRelativeToToday() {
    let today = InboxLogic.parseDay("2026-10-25")!
    #expect(InboxLogic.dueGroup("2026-10-21", today: today) == .overdue)
    #expect(InboxLogic.dueGroup("2026-10-25", today: today) == .today)
    #expect(InboxLogic.dueGroup("2026-10-28", today: today) == .soon)
    #expect(InboxLogic.dueGroup("2026-12-15", today: today) == .later)
    #expect(InboxLogic.dueGroup(nil, today: today) == .none)
}

@Test func appFiltersOrderByCount() {
    func loop(_ id: Int, _ app: String) -> Loop {
        Loop(id: id, title: "t", direction: "i_owe", counterparty: "c", deliverable: "d", note: nil, dueDate: nil,
             state: "open", closedReason: nil, sourceApp: app, bundleId: nil, windowTitle: nil, quote: nil, seen: 1,
             updatedAt: "", lastActionId: nil, lastActionStatus: nil, proofUrl: nil)
    }
    #expect(InboxLogic.appFilters([loop(1, "WhatsApp"), loop(2, "Google Chrome"), loop(3, "Google Chrome")])
            == ["Google Chrome", "WhatsApp"])
}

/// Real responses captured from the brain (anonymized): the Swift types must decode exactly what the API sends.
@Test func realBrainResponsesDecode() throws {
    func load<T: Decodable>(_ name: String, as type: T.Type) throws -> T {
        let url = try #require(Bundle.module.url(forResource: name, withExtension: "json", subdirectory: "Fixtures"))
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return try decoder.decode(T.self, from: Data(contentsOf: url))
    }
    let loops = try load("loops", as: [Loop].self)
    #expect(loops.count == 2)
    let closed = try #require(loops.first { $0.state == "closed" })
    #expect(closed.closedReason == "agent" && closed.proofUrl?.contains("thread-q3") == true && closed.lastActionStatus == "sent")
    let action = try load("action_sent", as: AgentAction.self)
    #expect(action.status == "sent" && action.draft?.to == ["test.recipient@example.com"] && !action.steps.isEmpty)
    _ = try load("memories", as: [Memory].self)
    let status = try load("status", as: BrainClient.Status.self)
    #expect(status.agentReady)
}

@Test func recipientsFieldParsesAndValidates() {
    #expect(InboxLogic.recipients("Rohan@College.example") == ["rohan@college.example"])
    #expect(InboxLogic.recipients("a@x.example, b@y.example") == ["a@x.example", "b@y.example"])
    #expect(InboxLogic.recipients("") == [])          // empty: Approve stays disabled
    #expect(InboxLogic.recipients("rohan") == nil)    // malformed
}
