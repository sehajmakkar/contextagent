import SwiftUI

/// The menu-bar panel: status, app filters, open loops (with "Close it for me"), and recently closed ones.
struct PanelView: View {
    let capture: AppModel
    let inbox: InboxModel
    @Environment(\.openWindow) private var openWindow
    @State private var showClosed = false

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            header
            StatusBanners(capture: capture, inbox: inbox)
            InboxList(inbox: inbox, capture: capture, compact: true)
            if !inbox.closed.isEmpty {
                DisclosureGroup(isExpanded: $showClosed) {
                    VStack(spacing: 6) {
                        ForEach(inbox.closed.prefix(8)) { ClosedLoopRow(loop: $0, inbox: inbox) }
                    }.padding(.top, 4)
                } label: {
                    Text("\(inbox.closed.count) closed").font(.caption).foregroundStyle(.secondary)
                }
            }
            Divider()
            footer
        }
        .padding(14)
        .frame(width: 400)
        .task {
            // While the panel is open, refresh every few seconds so a just-detected loop pops in live.
            while !Task.isCancelled {
                await inbox.refresh()
                await capture.refreshStatus()
                try? await Task.sleep(for: .seconds(3))
            }
        }
    }

    private var header: some View {
        HStack(alignment: .firstTextBaseline) {
            VStack(alignment: .leading, spacing: 2) {
                Text("Context Agent").font(.headline)
                HStack(spacing: 6) {
                    Text("\(inbox.open.count) open loops · \(inbox.closed.count) closed").font(.caption).foregroundStyle(.secondary)
                    if capture.isProcessing { PulseDot().help("Checking what you just looked at") }
                }
            }
            Spacer()
            Button { open("dashboard") } label: { Image(systemName: "rectangle.split.2x1") }.help("Open the dashboard")
            Button { open("settings") } label: { Image(systemName: "gearshape") }.help("Settings")
        }
        .buttonStyle(.borderless)
    }

    private var footer: some View {
        HStack(spacing: 8) {
            Image(systemName: capture.isPaused ? "pause.circle" : "eye").foregroundStyle(.secondary)
            if let event = capture.lastEvent {
                Text(verbatim: "\(event.app) · \(event.outcome)").lineLimit(1).foregroundStyle(.secondary)
            } else {
                Text(capture.isPaused ? "Capture paused" : "Watching for commitments").foregroundStyle(.secondary)
            }
            Spacer()
            Toggle("Pause", isOn: Binding(get: { capture.isPaused }, set: { capture.isPaused = $0 }))
                .toggleStyle(.switch).controlSize(.mini).labelsHidden().help("Pause capture")
            Button("Quit") { NSApplication.shared.terminate(nil) }.buttonStyle(.borderless)
        }
        .font(.caption)
    }

    private func open(_ id: String) {
        openWindow(id: id)
        NSApp.activate()
    }
}

/// Filter chips + the open loops, empty and error states included. Shared by the panel and the dashboard.
struct InboxList: View {
    let inbox: InboxModel
    let capture: AppModel
    let compact: Bool

    var body: some View {
        let apps = InboxLogic.appFilters(inbox.open)
        VStack(alignment: .leading, spacing: 8) {
            if apps.count > 1 {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 6) {
                        Chip(title: "All", selected: inbox.appFilter == nil) { inbox.appFilter = nil }
                        ForEach(apps, id: \.self) { app in
                            Chip(title: app, selected: inbox.appFilter == app) { inbox.appFilter = app }
                        }
                    }
                }
            }
            if inbox.visibleOpen.isEmpty {
                emptyState
            } else {
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 8) {
                        ForEach(inbox.visibleOpen) { loop in
                            LoopCard(loop: loop, inbox: inbox, agentReady: capture.brainStatus?.agentReady ?? false,
                                     agentHelp: capture.brainStatus?.agentDetail ?? "The brain isn't reachable.")
                        }
                    }
                }
                .frame(maxHeight: compact ? 470 : .infinity)
            }
        }
    }

    private var emptyState: some View {
        VStack(spacing: 6) {
            Image(systemName: "checkmark.circle").font(.title2).foregroundStyle(.green)
            Text("You're all set").font(.subheadline.weight(.semibold))
            Text("New commitments appear here when they show up on your screen.")
                .font(.caption).foregroundStyle(.secondary).multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 24)
    }
}

/// What needs your attention before anything else: permissions, the brain, the free tier, errors.
struct StatusBanners: View {
    let capture: AppModel
    let inbox: InboxModel

    var body: some View {
        VStack(spacing: 6) {
            if !capture.isTrusted {
                HStack {
                    Banner(symbol: "hand.raised", tint: .orange, text: "Allow Accessibility so Context Agent can read the window you're using. No screenshots, and password fields are never read.")
                    Button("Allow…") { capture.requestPermission() }.controlSize(.small)
                }
            }
            if capture.brainStatus == nil {
                Banner(symbol: "brain", tint: .red, text: "The brain isn't running. Start it with `make brain`.")
            } else if let status = capture.brainStatus {
                if !status.agentReady {
                    Banner(symbol: "envelope.badge.shield.half.filled", tint: .orange, text: "Close it for me is off: \(status.agentDetail)")
                }
            }
            if let error = inbox.error {
                Banner(symbol: "exclamationmark.triangle", tint: .red, text: error)
            }
        }
    }
}
