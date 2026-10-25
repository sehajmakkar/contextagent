import Foundation
import Testing
@testable import ContextAgent

private func snapshot(_ text: String, title: String = "Inbox - Gmail", bundle: String = "com.google.Chrome") -> WindowSnapshot {
    WindowSnapshot(appName: "Chrome", bundleID: bundle, windowTitle: title, url: nil, text: text,
                   nodesVisited: 1, truncated: false, elapsedMs: 1)
}

private let email = "Priya Sharma\nCan you send me the Q3 retention numbers before Thursday?"

@Test func settledAndLeavingReadsSendAtOnce() {
    var policy = CapturePolicy()
    // The quiet period (or leaving the app) already proves the text is stable: no second read needed.
    #expect(policy.decide(snapshot(email), trigger: .settled) == .send)
    #expect(policy.decide(snapshot(email), trigger: .leaving) == .skip(.unchanged))
    #expect(policy.decide(snapshot(email + "\nSure, will do"), trigger: .leaving) == .send)
}

@Test func coalescerWaitsForQuietButNotForever() {
    var c = EventCoalescer(quiet: 1.5, maxWait: 5)
    let t0 = Date(timeIntervalSince1970: 0)
    #expect(c.fireAt == nil)
    c.record(t0)
    #expect(c.fireAt == t0.addingTimeInterval(1.5))  // a single event: read after 1.5s of quiet
    c.record(t0.addingTimeInterval(1))
    #expect(c.fireAt == t0.addingTimeInterval(2.5))  // another event pushes it back…
    for s in stride(from: 2.0, through: 10.0, by: 1.0) { c.record(t0.addingTimeInterval(s)) }
    #expect(c.fireAt == t0.addingTimeInterval(5))    // …but a non-stop stream still reads by 5s
    c.reset()
    #expect(c.fireAt == nil)
}

@Test func sendsOnlyAfterTheScreenIsStable() {
    var policy = CapturePolicy()
    #expect(policy.decide(snapshot(email)) == .skip(.settling))  // first sight: wait
    #expect(policy.decide(snapshot(email)) == .send)             // same on the next read: send
    #expect(policy.decide(snapshot(email)) == .skip(.unchanged)) // already sent
}

@Test func halfTypedTextKeepsSettling() {
    var policy = CapturePolicy()
    #expect(policy.decide(snapshot(email + "\nSure, will")) == .skip(.settling))
    #expect(policy.decide(snapshot(email + "\nSure, will send by Wed")) == .skip(.settling))
}

@Test func clockAndBadgeChangesDoNotCountAsNew() {
    var policy = CapturePolicy()
    _ = policy.decide(snapshot("Inbox 12 · 10:41\n" + email))
    _ = policy.decide(snapshot("Inbox 12 · 10:41\n" + email))
    #expect(policy.decide(snapshot("Inbox 11 · 10:42\n" + email)) == .skip(.unchanged))
}

@Test func failedSendIsRetried() {
    var policy = CapturePolicy()
    _ = policy.decide(snapshot(email))
    #expect(policy.decide(snapshot(email)) == .send)
    policy.sendFailed(snapshot(email))
    #expect(policy.decide(snapshot(email)) == .send)
}

@Test func tinyScreensAreSkipped() {
    var policy = CapturePolicy()
    #expect(policy.decide(snapshot("Loading…")) == .skip(.tooShort))
}

@Test func passwordManagersAreNeverRead() {
    var policy = CapturePolicy()
    #expect(!policy.allows(bundleID: "com.1password.1password"))
    #expect(policy.allows(bundleID: "com.tinyspeck.slackmacgap"))
    policy.userExcluded = ["com.tinyspeck.slackmacgap"]
    #expect(!policy.allows(bundleID: "com.tinyspeck.slackmacgap"))
}

@Test func collectorCollapsesWhitespaceAndRepeats() {
    var collector = TextCollector(maxChars: 1_000)
    collector.add("Reply")
    collector.add("Reply")           // a link and its label child
    collector.add("  Hi   Sehaj,\n\nCan you   send it? ")
    #expect(collector.text == "Reply\nHi Sehaj,\nCan you send it?")
}

@Test func collectorStripsInvisibleDirectionMarks() {
    var collector = TextCollector(maxChars: 1_000)
    collector.add("\u{200E}Send")
    collector.add("Send")  // now equal to the previous line, so dropped as a repeat
    #expect(collector.text == "Send")
}

@Test func collectorStopsAtTheCap() {
    var collector = TextCollector(maxChars: 10)
    collector.add("abcdefghij")
    collector.add("more")
    #expect(collector.isFull && collector.lines == ["abcdefghij"])
}

@Test func oneHugeValueIsCutToTheCap() {
    var collector = TextCollector(maxChars: 10)
    collector.add("abc")
    collector.add(String(repeating: "x", count: 50_000))  // a whole source file in one AXValue
    #expect(collector.text == "abc\nxxxxxx" && collector.isFull)
}

@Test func offscreenFramesAreCulledButUnknownFramesAreNot() {
    let window = CGRect(x: 0, y: 0, width: 1000, height: 800)
    #expect(WindowTextReader.isVisible(CGRect(x: 10, y: 700, width: 500, height: 200), in: window))   // partly visible
    #expect(!WindowTextReader.isVisible(CGRect(x: 10, y: -3000, width: 500, height: 40), in: window)) // scrolled away
    #expect(WindowTextReader.isVisible(.zero, in: window))  // 0×0 container: unknown, keep walking
    #expect(!WindowTextReader.isVisible(CGRect(x: 21, y: 143, width: 587, height: 1), in: window)) // Chromium clamp
}

@Test func urlQueryStringsAreDropped() {
    let url = URL(string: "https://user:pw@example.com/reset?token=SECRET#inbox/FMfcg")!
    #expect(WindowTextReader.redactQuery(url) == "https://example.com/reset#inbox/FMfcg")
}

@Test func timestampsKeepTheLocalOffset() {
    let stamp = BrainClient.localTimestamp(Date(timeIntervalSince1970: 0))
    #expect(stamp.wholeMatch(of: /\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(Z|[+-]\d{2}:\d{2})/) != nil)
}
