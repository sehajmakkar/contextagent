import Foundation
import Testing
@testable import ContextAgent

private func snapshot(_ text: String, title: String = "Inbox - Gmail", bundle: String = "com.google.Chrome") -> WindowSnapshot {
    WindowSnapshot(appName: "Chrome", bundleID: bundle, windowTitle: title, url: nil, text: text,
                   nodesVisited: 1, truncated: false, elapsedMs: 1)
}

private let email = "Priya Sharma\nCan you send me the Q3 retention numbers before Thursday?"

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

@Test func urlQueryStringsAreDropped() {
    let url = URL(string: "https://user:pw@example.com/reset?token=SECRET#inbox/FMfcg")!
    #expect(WindowTextReader.redactQuery(url) == "https://example.com/reset#inbox/FMfcg")
}

@Test func timestampsKeepTheLocalOffset() {
    let stamp = BrainClient.localTimestamp(Date(timeIntervalSince1970: 0))
    #expect(stamp.wholeMatch(of: /\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(Z|[+-]\d{2}:\d{2})/) != nil)
}
