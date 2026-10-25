import SwiftUI

/// The dashboard window: your inbox next to recent memories (what the agent can draw on).
struct DashboardView: View {
    let capture: AppModel
    let inbox: InboxModel

    var body: some View {
        HStack(alignment: .top, spacing: 16) {
            VStack(alignment: .leading, spacing: 10) {
                Text("Your Inbox").font(.title2.weight(.semibold))
                HStack(spacing: 8) {
                    Text("\(inbox.open.count) open loops · \(inbox.closed.count) closed").foregroundStyle(.secondary)
                    if capture.isProcessing { PulseDot().help("Checking what you just looked at") }
                }
                StatusBanners(capture: capture, inbox: inbox)
                InboxList(inbox: inbox, capture: capture, compact: false)
                if !inbox.closed.isEmpty {
                    Text("Recently closed").font(.headline).padding(.top, 6)
                    ForEach(inbox.closed.prefix(6)) { ClosedLoopRow(loop: $0, inbox: inbox) }
                }
            }
            .frame(minWidth: 460, maxWidth: .infinity, alignment: .topLeading)
            .padding(18)
            .background(RoundedRectangle(cornerRadius: 14).fill(.background.secondary))

            VStack(alignment: .leading, spacing: 10) {
                Text("Recent memories").font(.title3.weight(.semibold))
                if inbox.memories.isEmpty {
                    Text("Memories appear after your first episodes are processed.").foregroundStyle(.secondary).font(.callout)
                }
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 12) {
                        ForEach(inbox.memories) { memory in
                            HStack(alignment: .top, spacing: 10) {
                                AppIcon(bundleID: memory.bundleId, size: 22)
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(verbatim: memory.text).fixedSize(horizontal: false, vertical: true)
                                    Text(verbatim: "\(memory.kind) · \(memory.happenedAt.prefix(10))")
                                        .font(.caption).foregroundStyle(.secondary)
                                }
                            }
                        }
                    }
                }
            }
            .frame(width: 340, alignment: .topLeading)
            .padding(18)
            .background(RoundedRectangle(cornerRadius: 14).fill(.background.secondary))
        }
        .padding(16)
        .frame(minWidth: 860, minHeight: 560)
        .task {
            while !Task.isCancelled {
                await inbox.refresh()
                await capture.refreshStatus()
                try? await Task.sleep(for: .seconds(3))
            }
        }
    }
}
