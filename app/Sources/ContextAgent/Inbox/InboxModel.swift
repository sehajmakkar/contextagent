import Foundation
import Observation

/// Inbox state: open and closed loops, recent memories, and each loop's "Close it for me" run.
@MainActor
@Observable
final class InboxModel {
    struct StepLine: Identifiable, Equatable {
        let id: Int
        let label: String
        let status: String  // ok | refused | error | running
    }

    enum Phase: Equatable {
        case running
        case draft(AgentAction)         // waiting for you: review, edit, approve or reject
        case sending(AgentAction)
        case sent(AgentAction)
        case finished(AgentAction)      // already_done / cannot_close / failed: nothing to send
        case failed(String)
    }

    struct Run: Equatable {
        var steps: [StepLine] = []
        var phase: Phase = .running
        var editedBody = ""
        var editedTo = ""    // new emails only: the recipient you type in
        var error: String?   // shown on the card itself, so a background refresh can't wipe it
    }

    private(set) var open: [Loop] = []
    private(set) var closed: [Loop] = []
    private(set) var memories: [Memory] = []
    private(set) var runs: [Int: Run] = [:]
    private(set) var lastRefresh: Date?
    var error: String?
    var appFilter: String?

    private let brain = BrainClient()
    private var polling = false

    var visibleOpen: [Loop] { open.filter { appFilter == nil || $0.sourceApp == appFilter } }

    func startPolling() {
        guard !polling else { return }
        polling = true
        Task {
            while true {
                await refresh()
                try? await Task.sleep(for: .seconds(15))
            }
        }
    }

    func refresh() async {
        do {
            async let openLoops = brain.loops(state: "open")
            async let closedLoops = brain.loops(state: "closed")
            async let recent = brain.memories(limit: 30)
            let (newOpen, newClosed, newMemories) = try await (openLoops, closedLoops, recent)
            // Assign only on change: every assignment redraws every card, even when nothing moved.
            if newOpen != open { open = newOpen }
            if newClosed != closed { closed = newClosed }
            if newMemories != memories { memories = newMemories }
            error = nil
            lastRefresh = .now
            await resumePendingDrafts()
        } catch {
            self.error = error.localizedDescription
        }
    }

    /// A draft waiting for approval survives an app restart: reload it from the brain.
    private func resumePendingDrafts() async {
        for loop in open where loop.state == "awaiting_approval" && runs[loop.id] == nil {
            guard let actionID = loop.lastActionId, let action = try? await brain.action(actionID),
                  action.status == "awaiting_approval" else { continue }
            runs[loop.id] = Run(steps: [], phase: .draft(action), editedBody: action.draft?.body ?? "",
                                editedTo: action.draft?.to.joined(separator: ", ") ?? "")
        }
    }

    // MARK: - Close it for me

    func closeItForMe(_ loop: Loop) async {
        runs[loop.id] = Run()
        do {
            for try await event in brain.closeStream(loopID: loop.id) {
                apply(event, to: loop.id)
            }
        } catch {
            runs[loop.id]?.phase = .failed(error.localizedDescription)
        }
        await refresh()
    }

    private func apply(_ event: AgentEvent, to loopID: Int) {
        guard var run = runs[loopID] else { return }
        switch event {
        case .thinking:
            break
        case let .step(_, status, label):
            run.steps.append(StepLine(id: run.steps.count, label: label, status: status))
        case let .done(action):
            if action.status == "awaiting_approval", let draft = action.draft {
                run.phase = .draft(action)
                run.editedBody = draft.body
                run.editedTo = draft.to.joined(separator: ", ")
            } else {
                run.phase = .finished(action)
            }
        case let .failed(detail):
            run.phase = .failed(detail)
        }
        runs[loopID] = run
    }

    func editBody(_ loopID: Int, _ body: String) {
        runs[loopID]?.editedBody = body
    }

    func editTo(_ loopID: Int, _ to: String) {
        runs[loopID]?.editedTo = to
    }

    /// Approve & Send: sends the hash of the draft you were shown, plus your edits (ADR-046).
    func approve(_ loopID: Int) async {
        guard let run = runs[loopID], case let .draft(action) = run.phase, let draft = action.draft else { return }
        guard InboxLogic.placeholders(in: run.editedBody).isEmpty else { return }  // also disabled in the UI
        runs[loopID]?.phase = .sending(action)
        runs[loopID]?.error = nil
        do {
            let edited = run.editedBody == draft.body ? nil : run.editedBody
            // Only a new email's recipients are yours to set; a reply's stay pinned to its thread.
            let to = draft.isNewEmail ? InboxLogic.recipients(run.editedTo) : nil
            let result = try await brain.approve(actionID: action.id, draftHash: draft.draftHash, editedBody: edited, to: to)
            runs[loopID]?.phase = .sent(result)
        } catch {
            // Nothing was sent; the brain keeps the draft awaiting approval, so the button works again.
            runs[loopID]?.phase = .draft(action)
            runs[loopID]?.error = error.localizedDescription
        }
        await refresh()
    }

    func reject(_ loopID: Int) async {
        guard let run = runs[loopID], case let .draft(action) = run.phase else { return }
        do {
            _ = try await brain.reject(actionID: action.id, reason: "rejected in the inbox")
            runs[loopID] = nil
        } catch {
            runs[loopID]?.error = error.localizedDescription
        }
        await refresh()
    }

    func dismissRun(_ loopID: Int) {
        runs[loopID] = nil
    }

    // MARK: - Resolve / not a loop / reopen

    func resolve(_ loop: Loop) async { await move(loop, to: "closed", reason: "resolved in the inbox") }
    func notALoop(_ loop: Loop) async { await move(loop, to: "dismissed", reason: "not a loop (inbox)") }
    func reopen(_ loop: Loop) async { await move(loop, to: "open", reason: "reopened in the inbox") }

    private func move(_ loop: Loop, to state: String, reason: String) async {
        do {
            try await brain.transition(loopID: loop.id, to: state, reason: reason)
            runs[loop.id] = nil
        } catch {
            self.error = error.localizedDescription
        }
        await refresh()
    }

    func deleteAllData() async {
        do {
            try await brain.deleteAllData()
            runs = [:]
        } catch {
            self.error = error.localizedDescription
        }
        await refresh()
    }
}
