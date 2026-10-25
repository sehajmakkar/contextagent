import SwiftUI

/// One open loop, Minimi-style: source app · window · due, the title, why it's open, and the quote that proves it.
struct LoopCard: View {
    let loop: Loop
    let inbox: InboxModel
    let agentReady: Bool
    var agentHelp: String = ""

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 6) {
                Circle().fill(dotColor).frame(width: 6, height: 6)
                AppIcon(bundleID: loop.bundleId, size: 16)
                Text(verbatim: "· \(loop.windowTitle ?? loop.sourceApp ?? "")").lineLimit(1).foregroundStyle(.secondary)
                Spacer(minLength: 4)
                DueBadge(due: loop.dueDate)
            }
            .font(.caption)

            Text(verbatim: loop.title).font(.system(size: 13, weight: .semibold)).fixedSize(horizontal: false, vertical: true)
            Text(verbatim: directionLabel(loop) + (loop.note.map { " · \($0)" } ?? ""))
                .font(.caption).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
            if let quote = loop.quote {
                Text(verbatim: "Source: “\(quote)”").font(.caption).foregroundStyle(.tertiary).lineLimit(3)
            }

            if let run = inbox.runs[loop.id] {
                AgentRunView(loopID: loop.id, run: run, inbox: inbox).padding(.top, 2)
            } else {
                actions
            }
        }
        .padding(10)
        .background(RoundedRectangle(cornerRadius: 10).fill(Color.secondary.opacity(0.06)))
    }

    private var actions: some View {
        HStack(spacing: 8) {
            if loop.direction != "self" {
                // The differentiator: Minimi resolves, we close it for you (with your approval).
                Button { Task { await inbox.closeItForMe(loop) } } label: { Label("Close it for me", systemImage: "sparkles") }
                    .buttonStyle(.borderedProminent)
                    .disabled(!agentReady || loop.state != "open")
                    .help(agentReady ? "The agent drafts the reply in the thread. Nothing is sent without you." : agentHelp)
            }
            Button("Resolve") { Task { await inbox.resolve(loop) } }
            Spacer()
            Menu {
                Button("Not a loop") { Task { await inbox.notALoop(loop) } }
            } label: { Image(systemName: "ellipsis") }
                .menuStyle(.borderlessButton).menuIndicator(.hidden).fixedSize()
        }
        .controlSize(.small)
    }

    private var dotColor: Color {
        switch InboxLogic.dueGroup(loop.dueDate) {
        case .overdue: .red
        case .today: .orange
        default: .yellow
        }
    }
}

/// A closed loop, with how it was closed and, if the agent sent it, a link to the email.
struct ClosedLoopRow: View {
    let loop: Loop
    let inbox: InboxModel

    var body: some View {
        HStack(spacing: 8) {
            AppIcon(bundleID: loop.bundleId, size: 14)
            VStack(alignment: .leading, spacing: 1) {
                Text(verbatim: loop.title).font(.caption).strikethrough().lineLimit(1)
                Text(verbatim: closedHow).font(.caption2).foregroundStyle(.secondary)
            }
            Spacer()
            if let url = loop.proofUrl.flatMap(URL.init(string:)) {
                Link(destination: url) { Image(systemName: "envelope.open") }.help("Open the sent email")
            }
            Button { Task { await inbox.reopen(loop) } } label: { Image(systemName: "arrow.uturn.backward") }
                .buttonStyle(.borderless).help("Reopen")
        }
    }

    private var closedHow: String {
        switch loop.closedReason {
        case "agent": "Closed by the agent: sent with your approval"
        case "inferred": "Closed automatically: the screen showed it was done"
        default: "Resolved by you"
        }
    }
}
