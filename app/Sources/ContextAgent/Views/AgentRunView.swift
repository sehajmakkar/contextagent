import SwiftUI

/// "Close it for me" in progress: live steps, then the draft to review, edit, approve or reject.
struct AgentRunView: View {
    let loopID: Int
    let run: InboxModel.Run
    let inbox: InboxModel

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            if !run.steps.isEmpty || run.phase == .running {
                VStack(alignment: .leading, spacing: 3) {
                    ForEach(run.steps) { step in
                        HStack(spacing: 6) {
                            Image(systemName: step.status == "ok" ? "checkmark.circle.fill" : "xmark.octagon.fill")
                                .foregroundStyle(step.status == "ok" ? .green : .orange)
                            // A refused step is a guardrail doing its job (e.g. an outside recipient): show it.
                            Text(verbatim: step.status == "ok" ? step.label : "\(step.label): refused by a guardrail")
                        }
                    }
                    if run.phase == .running {
                        HStack(spacing: 6) {
                            ProgressView().controlSize(.mini)
                            Text(run.steps.isEmpty ? "Starting…" : "Thinking…").foregroundStyle(.secondary)
                        }
                    }
                }
                .font(.caption)
            }

            switch run.phase {
            case .running:
                EmptyView()
            case let .draft(action), let .sending(action):
                if let draft = action.draft { DraftReview(loopID: loopID, action: action, draft: draft, run: run, inbox: inbox) }
            case let .sent(action):
                Banner(symbol: "paperplane.fill", tint: .green,
                       text: action.status == "sent" ? "Sent, and confirmed in your Sent folder. Loop closed."
                                                     : "Sent, but it couldn't be confirmed in Sent yet.")
            case let .finished(action):
                VStack(alignment: .leading, spacing: 6) {
                    Banner(symbol: action.outcome == "already_done" ? "checkmark.seal" : "info.circle", tint: .blue,
                           text: outcomeText(action))
                    HStack {
                        Button("OK") { inbox.dismissRun(loopID) }.controlSize(.small)
                    }
                }
            case let .failed(detail):
                VStack(alignment: .leading, spacing: 6) {
                    Banner(symbol: "exclamationmark.triangle", tint: .red, text: detail)
                    Button("OK") { inbox.dismissRun(loopID) }.controlSize(.small)
                }
            }
        }
    }

    private func outcomeText(_ action: AgentAction) -> String {
        let summary = action.summary ?? ""
        switch action.outcome {
        case "already_done": return "Looks already done. \(summary) Resolve it if that's right."
        case "cannot_close": return "An email can't close this one. \(summary)"
        default: return summary.isEmpty ? "The agent stopped without a draft." : summary
        }
    }
}

private struct DraftReview: View {
    let loopID: Int
    let action: AgentAction
    let draft: Draft
    let run: InboxModel.Run
    let inbox: InboxModel
    // The editors own their text. Binding them to `run` (a copy taken when this view was built) handed the
    // stale string back after every keystroke, so the text view reset and the cursor jumped to the end.
    @State private var text: String
    @State private var toText: String

    init(loopID: Int, action: AgentAction, draft: Draft, run: InboxModel.Run, inbox: InboxModel) {
        (self.loopID, self.action, self.draft, self.run, self.inbox) = (loopID, action, draft, run, inbox)
        _text = State(initialValue: run.editedBody)
        _toText = State(initialValue: run.editedTo)
    }

    var body: some View {
        let placeholders = InboxLogic.placeholders(in: text)
        let sending = if case .sending = run.phase { true } else { false }
        let recipients = draft.isNewEmail ? InboxLogic.recipients(toText) : draft.to
        let recipientOK = !(recipients ?? []).isEmpty

        VStack(alignment: .leading, spacing: 6) {
            if draft.isNewEmail {
                Label("New email · not a reply (no existing thread)", systemImage: "square.and.pencil")
                    .font(.caption2.weight(.medium)).foregroundStyle(.blue)
            }
            Grid(alignment: .leading, horizontalSpacing: 6, verticalSpacing: 2) {
                GridRow {
                    Text("To").foregroundStyle(.secondary)
                    if draft.isNewEmail {
                        // You choose who a new email goes to; the agent may only suggest the loop's known contact.
                        TextField("name@example.com", text: $toText)
                            .textFieldStyle(.roundedBorder).disabled(sending)
                            .onChange(of: toText) { inbox.editTo(loopID, toText) }
                    } else {
                        Text(verbatim: draft.to.joined(separator: ", ")).textSelection(.enabled)
                    }
                }
                GridRow {
                    Text("Subject").foregroundStyle(.secondary)
                    Text(verbatim: draft.subject).lineLimit(1)
                }
            }
            .font(.caption)

            TextEditor(text: $text)
                .font(.system(size: 12))
                .frame(minHeight: 120, maxHeight: 220)
                .scrollContentBackground(.hidden)
                .padding(6)
                .background(RoundedRectangle(cornerRadius: 6).fill(Color(nsColor: .textBackgroundColor)))
                .overlay(RoundedRectangle(cornerRadius: 6).stroke(.quaternary))
                .disabled(sending)
                .onChange(of: text) { inbox.editBody(loopID, text) }

            if let error = run.error {
                Banner(symbol: "exclamationmark.triangle.fill", tint: .red, text: error)
            }
            if draft.isNewEmail && !recipientOK {
                Banner(symbol: "person.crop.circle.badge.questionmark", tint: .orange,
                       text: recipients == nil ? "That doesn't look like an email address." : "Add who this goes to.")
            }
            if !placeholders.isEmpty {
                Banner(symbol: "pencil.and.list.clipboard", tint: .orange,
                       text: "Fill in before sending: " + placeholders.joined(separator: " · "))
            } else if !action.missingInfo.isEmpty, text == draft.body {
                Banner(symbol: "exclamationmark.bubble", tint: .orange,
                       text: "Check before sending: " + action.missingInfo.joined(separator: " · "))
            }

            HStack {
                Button(role: .destructive) { Task { await inbox.reject(loopID) } } label: { Text("Reject") }
                    .disabled(sending)
                Spacer()
                if sending { ProgressView().controlSize(.small) }
                // The only path that sends email, and only for the draft on screen (ADR-046).
                Button { Task { await inbox.approve(loopID) } } label: { Label("Approve & Send", systemImage: "paperplane") }
                    .buttonStyle(.borderedProminent)
                    .disabled(sending || !placeholders.isEmpty || !recipientOK
                              || text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                    .help(!recipientOK ? "Add a recipient first" : placeholders.isEmpty ? "Send exactly this email"
                                                                                       : "Fill in the [[placeholders]] first")
            }
            .controlSize(.small)
        }
    }
}
