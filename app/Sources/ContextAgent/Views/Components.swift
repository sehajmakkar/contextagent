import AppKit
import SwiftUI

/// The real icon of the app a loop or memory came from (provenance at a glance), cached per bundle ID.
struct AppIcon: View {
    let bundleID: String?
    var size: CGFloat = 18

    @MainActor private static var cache: [String: NSImage] = [:]

    var body: some View {
        if let image = Self.icon(for: bundleID) {
            Image(nsImage: image).resizable().frame(width: size, height: size)
        } else {
            Image(systemName: "app.dashed").frame(width: size, height: size).foregroundStyle(.secondary)
        }
    }

    @MainActor private static func icon(for bundleID: String?) -> NSImage? {
        guard let bundleID else { return nil }
        if let cached = cache[bundleID] { return cached }
        guard let url = NSWorkspace.shared.urlForApplication(withBundleIdentifier: bundleID) else { return nil }
        let image = NSWorkspace.shared.icon(forFile: url.path)
        cache[bundleID] = image
        return image
    }
}

struct Chip: View {
    let title: String
    let selected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Text(verbatim: title).font(.caption).lineLimit(1)
                .padding(.horizontal, 10).padding(.vertical, 4)
                .background(Capsule().fill(selected ? Color.accentColor.opacity(0.25) : Color.secondary.opacity(0.12)))
                .overlay(Capsule().stroke(selected ? Color.accentColor : .clear, lineWidth: 1))
        }
        .buttonStyle(.plain)
    }
}

struct DueBadge: View {
    let due: String?

    var body: some View {
        let group = InboxLogic.dueGroup(due)
        if let due, group != .none {
            Text(verbatim: group == .overdue ? "overdue · \(due)" : group == .today ? "due today" : "due \(due)")
                .font(.caption2.weight(.medium))
                .padding(.horizontal, 6).padding(.vertical, 2)
                .background(Capsule().fill(color(group).opacity(0.18)))
                .foregroundStyle(color(group))
        }
    }

    private func color(_ group: InboxLogic.DueGroup) -> Color {
        switch group {
        case .overdue: .red
        case .today: .orange
        default: .secondary
        }
    }
}

struct Banner: View {
    let symbol: String
    let tint: Color
    let text: String

    var body: some View {
        HStack(alignment: .top, spacing: 8) {
            Image(systemName: symbol).foregroundStyle(tint)
            Text(verbatim: text).font(.caption).fixedSize(horizontal: false, vertical: true)
            Spacer(minLength: 0)
        }
        .padding(8)
        .background(RoundedRectangle(cornerRadius: 8).fill(tint.opacity(0.10)))
    }
}

/// Who owes whom, as Minimi-style plain words.
func directionLabel(_ loop: Loop) -> String {
    switch loop.direction {
    case "they_owe": "\(loop.counterparty) owes you"
    case "self": "Reminder to yourself"
    default: "You owe \(loop.counterparty)"
    }
}

/// A quiet "working on it" signal: a small dot that breathes. No spinner, no text (Minimi shows nothing at all).
struct PulseDot: View {
    @State private var dim = false

    var body: some View {
        Circle().fill(Color.accentColor).frame(width: 7, height: 7)
            .opacity(dim ? 0.25 : 1)
            .animation(.easeInOut(duration: 0.9).repeatForever(autoreverses: true), value: dim)
            .onAppear { dim = true }
    }
}
