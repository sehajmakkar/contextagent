import SwiftUI

/// The menu-bar panel: a glance at what's open. All the work happens in the dashboard.
struct PanelView: View {
    let capture: AppModel
    let inbox: InboxModel
    @Environment(\.openWindow) private var openWindow
    @State private var showClosed = false

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            header
            StatusBanners(capture: capture, inbox: inbox, compact: true)
            loopList
            Divider()
            footer
        }
        .padding(14)
        .frame(width: 360)
        .task {
            // While the panel is open, refresh every few seconds so a just-detected loop pops in live.
            while !Task.isCancelled {
                await inbox.refresh()
                await capture.refreshStatus()
                try? await Task.sleep(for: .seconds(3))
            }
        }
    }

    /// Just what's open: app icon + title. Everything else (close, resolve, drafts) lives in the dashboard.
    /// A plain stack, not a ScrollView: inside a menu-bar window a ScrollView can collapse to zero height.
    private var loopList: some View {
        VStack(alignment: .leading, spacing: 2) {
            if inbox.open.isEmpty {
                Text("No open loops. You're all set.").font(.callout).foregroundStyle(.secondary).padding(.vertical, 8)
            }
            ForEach(inbox.open.prefix(Self.maxRows)) { loop in
                Button { open("dashboard") } label: {
                    HStack(spacing: 10) {
                        AppIcon(bundleID: loop.bundleId, size: 20)
                        Text(verbatim: loop.title).font(.system(size: 13)).lineLimit(2)
                            .multilineTextAlignment(.leading).frame(maxWidth: .infinity, alignment: .leading)
                    }
                    .padding(.vertical, 6).padding(.horizontal, 6)
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .help("Open the dashboard")
            }
            if inbox.open.count > Self.maxRows {
                Text("+\(inbox.open.count - Self.maxRows) more in the dashboard").font(.caption).foregroundStyle(.secondary)
                    .padding(.horizontal, 6)
            }
        }
    }

    private static let maxRows = 8

    private var header: some View {
        HStack(alignment: .firstTextBaseline) {
            VStack(alignment: .leading, spacing: 2) {
                Text("Context Agent").font(.headline)
                HStack(spacing: 6) {
                    Text("\(inbox.open.count) open loops").font(.caption).foregroundStyle(.secondary)
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

/// The dashboard's inbox: filter chips + open loop cards, empty state included.
struct InboxList: View {
    let inbox: InboxModel
    let capture: AppModel
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
            }
        }
    }

    private var emptyState: some View {
        VStack(spacing: 6) {
            Image(systemName: "checkmark.circle").font(.largeTitle).foregroundStyle(.green)
            Text("You're all set").font(.title3.weight(.semibold))
            Text("New commitments appear here when they show up on your screen.")
                .font(.body).foregroundStyle(.secondary).multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 24)
    }
}

/// What needs your attention before anything else: permissions, the brain, the free tier, errors.
struct StatusBanners: View {
    let capture: AppModel
    let inbox: InboxModel
    var compact = false

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
                if !status.agentReady && !compact {
                    Banner(symbol: "envelope.badge.shield.half.filled", tint: .orange, text: "Close it for me is off: \(status.agentDetail)")
                }
            }
            if let error = inbox.error {
                Banner(symbol: "exclamationmark.triangle", tint: .red, text: error)
            }
        }
    }
}
