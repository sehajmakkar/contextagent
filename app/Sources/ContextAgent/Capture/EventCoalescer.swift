import Foundation

/// Turns a burst of change notifications into one read: debounce with a max wait.
///
/// - Debounce: read `quiet` seconds after the *last* event, so a page that's still loading
///   or a sentence being typed is read once it settles.
/// - Max wait: never later than `maxWait` after the *first* event, so continuous changes
///   (a chat streaming in, non-stop typing) still get read at least every few seconds.
struct EventCoalescer {
    var quiet: TimeInterval = 1.5
    var maxWait: TimeInterval = 5

    private(set) var firstEventAt: Date?
    private(set) var lastEventAt: Date?

    mutating func record(_ now: Date) {
        if firstEventAt == nil { firstEventAt = now }
        lastEventAt = now
    }

    /// When the pending read should happen, or nil if nothing is pending.
    var fireAt: Date? {
        guard let first = firstEventAt, let last = lastEventAt else { return nil }
        return min(last.addingTimeInterval(quiet), first.addingTimeInterval(maxWait))
    }

    mutating func reset() {
        firstEventAt = nil
        lastEventAt = nil
    }
}
