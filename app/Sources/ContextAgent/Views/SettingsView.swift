import SwiftUI

/// Settings: capture controls, what leaves your Mac, and deleting everything.
struct SettingsView: View {
    let capture: AppModel
    let inbox: InboxModel
    @State private var confirmDelete = false

    var body: some View {
        Form {
            Section("Capture") {
                Toggle("Pause capture", isOn: Binding(get: { capture.isPaused }, set: { capture.isPaused = $0 }))
                LabeledContent("Accessibility") {
                    if capture.isTrusted {
                        Label("Allowed", systemImage: "checkmark.circle").foregroundStyle(.green)
                    } else {
                        Button("Allow…") { capture.requestPermission() }
                    }
                }
                LabeledContent("Never captured") {
                    Text("Password managers, Keychain, System Settings, and password fields in every app")
                        .foregroundStyle(.secondary).multilineTextAlignment(.trailing)
                }
                if capture.userExcluded.isEmpty {
                    LabeledContent("Excluded by you") { Text("None").foregroundStyle(.secondary) }
                } else {
                    LabeledContent("Excluded by you") {
                        VStack(alignment: .trailing) {
                            ForEach(capture.userExcluded.sorted(), id: \.self) { Text(verbatim: $0).font(.caption) }
                            Button("Clear all") { capture.clearExclusions() }.controlSize(.small)
                        }
                    }
                }
            }

            Section("What leaves your Mac") {
                Text("Stored only on this Mac: everything captured, your memories and their vectors, loops, and the audit log (~/Library/Application Support/ContextAgent).")
                Text("Sent to Gemini, encrypted in transit: the text of each finished visit to a window (to extract memories and loops), memory text for embeddings, and the email thread the agent is working on. Pause capture whenever you don't want your screen read.")
                Text("Sent by email: only a draft you approved, to people already in that thread.")
                if let status = capture.brainStatus {
                    LabeledContent("Agent") { Text(verbatim: status.agentDetail).foregroundStyle(.secondary) }
                }
            }
            .font(.callout)

            Section("Danger zone") {
                Button("Delete all data…", role: .destructive) { confirmDelete = true }
                    .confirmationDialog("Delete every capture, memory, loop and audit record?", isPresented: $confirmDelete) {
                        Button("Delete everything", role: .destructive) { Task { await inbox.deleteAllData() } }
                    } message: {
                        Text("This can't be undone. Your Gmail and its drafts aren't touched.")
                    }
            }
        }
        .formStyle(.grouped)
        .frame(width: 520, height: 560)
    }
}
