import SwiftUI

/// The dashboard window: your inbox next to recent memories (what the agent can draw on).
struct DashboardView: View {
    let capture: AppModel
    let inbox: InboxModel

    var body: some View {
        HStack(alignment: .top, spacing: 16) {
            VStack(alignment: .leading, spacing: 10) {
                Text("Your Inbox").font(.largeTitle.weight(.bold))
                HStack(spacing: 8) {
                    Text("\(inbox.open.count) open loops · \(inbox.closed.count) closed").font(.title3).foregroundStyle(.secondary)
                    if capture.isProcessing { PulseDot().help("Checking what you just looked at") }
                }
                StatusBanners(capture: capture, inbox: inbox)
                InboxList(inbox: inbox, capture: capture)
                if !inbox.closed.isEmpty {
                    Text("Recently closed").font(.title3.weight(.semibold)).padding(.top, 8)
                    ForEach(inbox.closed.prefix(6)) { ClosedLoopRow(loop: $0, inbox: inbox) }
                }
            }
            .frame(minWidth: 560, maxWidth: .infinity, alignment: .topLeading)
            .padding(22)
            .background(RoundedRectangle(cornerRadius: 14).fill(.background.secondary))

            VStack(alignment: .leading, spacing: 10) {
                Text("Recent memories").font(.title2.weight(.bold))
                if inbox.memories.isEmpty {
                    Text("Memories appear after your first episodes are processed.").foregroundStyle(.secondary).font(.body)
                }
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 16) {
                        ForEach(inbox.memories) { memory in
                            HStack(alignment: .top, spacing: 10) {
                                AppIcon(bundleID: memory.bundleId, size: 28)
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(verbatim: memory.text).font(.system(size: 16)).fixedSize(horizontal: false, vertical: true)
                                    Text(verbatim: "\(memory.kind) · \(memory.happenedAt.prefix(10))")
                                        .font(.callout).foregroundStyle(.secondary)
                                }
                            }
                        }
                    }
                }
            }
            .frame(width: 400, alignment: .topLeading)
            .padding(22)
            .background(RoundedRectangle(cornerRadius: 14).fill(.background.secondary))
        }
        .padding(16)
        .frame(minWidth: 1040, minHeight: 680)
        .task {
            while !Task.isCancelled {
                await inbox.refresh()
                await capture.refreshStatus()
                try? await Task.sleep(for: .seconds(3))
            }
        }
    }
}
