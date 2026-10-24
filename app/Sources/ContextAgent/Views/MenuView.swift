import SwiftUI

/// The menu-bar panel. Phase 2 keeps it to status and controls; the loops inbox arrives in Phase 6.
struct MenuView: View {
    @Bindable var model: AppModel

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Context Agent").font(.headline)

            if !model.isTrusted {
                Card(symbol: "hand.raised", tint: .orange, title: "Accessibility permission needed") {
                    Text("Context Agent reads the text of the window you're using through macOS Accessibility. "
                        + "No screenshots. Password fields and apps like 1Password are never read.")
                    Button("Open Accessibility Settings…") { model.requestPermission() }
                }
            }

            brainCard
            if let status = model.brainStatus, !status.liveDetectionAllowed {
                Card(symbol: "lock.shield", tint: .blue, title: "Free tier: captures stay on this Mac") {
                    Text("\(status.heldBack) capture(s) stored locally and not sent to Gemini. "
                        + "Use a paid key, or test data with ALLOW_FREE_TIER_LIVE=true.")
                }
            }

            captureCard

            Divider()
            HStack {
                Toggle("Pause capture", isOn: $model.isPaused).toggleStyle(.switch).controlSize(.small)
                Spacer()
                Button("Quit") { NSApplication.shared.terminate(nil) }
            }
        }
        .padding(14)
        .frame(width: 340)
    }

    @ViewBuilder private var brainCard: some View {
        if let status = model.brainStatus {
            Card(symbol: "brain", tint: .green, title: "Brain connected · \(status.tier) tier") {
                Text("\(status.captured) captured · \(status.pending) pending · \(status.openLoops) open loop(s)")
                if let error = status.lastError {
                    Text("Last detection error: \(error)").foregroundStyle(.red)
                }
            }
        } else {
            Card(symbol: "brain", tint: .red, title: "Brain not reachable") {
                Text(model.brainError ?? "Start it with `make brain`.")
            }
        }
    }

    @ViewBuilder private var captureCard: some View {
        Card(symbol: model.isPaused ? "pause.circle" : "eye", tint: .secondary, title: "Last capture") {
            if let event = model.lastEvent {
                // Plain Text(verbatim:) so captured titles are never parsed as Markdown.
                Text(verbatim: "\(event.app) · \(event.title)").lineLimit(2)
                Text(verbatim: "\(event.chars) chars · \(event.elapsedMs) ms · \(event.outcome)")
                    .foregroundStyle(.secondary)
                Text(event.at, style: .relative).foregroundStyle(.secondary)
            } else {
                Text("Nothing yet").foregroundStyle(.secondary)
            }
            if let app = model.lastApp, !model.userExcluded.contains(app.bundleID) {
                Button("Never capture \(app.name)") { model.exclude(app) }
            }
            if !model.userExcluded.isEmpty {
                Button("Clear \(model.userExcluded.count) excluded app(s)") { model.clearExclusions() }
            }
        }
    }
}

private struct Card<Content: View>: View {
    let symbol: String
    let tint: Color
    let title: String
    @ViewBuilder let content: Content

    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: symbol).foregroundStyle(tint).frame(width: 18)
            VStack(alignment: .leading, spacing: 4) {
                Text(title).font(.subheadline.weight(.semibold))
                content.font(.caption)
            }
        }
    }
}
