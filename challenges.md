# Challenges

Hard problems we hit, how we worked them out, and what came of it. Each entry is written so you can retell it in an interview or a cold DM: **situation → why it was hard → what we tried → what worked → result → tradeoff.**

Status: ✅ solved · 🟡 partly solved / stopgap · 🔵 proposed (not built yet)

| # | Challenge | Phase | Status |
|---|---|---|---|
| 1 | Over-capture: a code editor sent a 25,000-char file on every read | 2 → 3 | 🟡 capped; full fix proposed |
| 2 | Gmail's navigation drowned the actual email | 2 | ✅ −28% chars |
| 3 | Near-duplicate screens: three designs before one worked | 2 | ✅ |
| 4 | The Accessibility permission kept "forgetting" the app | 2 | ✅ |
| 5 | Chrome, Slack and Cursor returned almost no text | 2 | ✅ |
| 6 | Real-app text was dirty: duplicated drafts, invisible characters | 2 | ✅ |
| 7 | A localhost API that any web page could reach | 2 | ✅ |
| 8 | Free API tier vs privacy | 0–2 | ✅ |
| 9 | Model output broke the UI (markup injection) | 1 | ✅ |
| 10 | Failed LLM calls silently lost work | 1 | ✅ |
| 11 | Closing loops in many apps, not just Gmail | 5 (design) | 🔵 |
| 12 | Detection missed meeting action items | 1 | 🔵 your prompt exercise |
| 13 | Polling misses short-lived screens, and faster polling just makes duplicates | 2 → 3 | 🔵 proposed |

---

## 1. Over-capture: 20,000+ characters per read 🟡

**Situation.** Reading Cursor's window returned 25,898 characters, because a code editor exposes the **entire open file** as one accessibility value. Gmail threads include off-screen messages too. Sending whole screens to the LLM wastes tokens and rate limit, and storing them wastes disk while keeping private text we don't need.
**Why it's hard.** It has to be **fast** (capture can't wait on an LLM) and must not drop the one line that matters (a new "can you send it by Friday?").
**Done so far.** A hard cap: a single huge value is cut to the remaining 20k budget, with a test.
**Proposed (Phase 3).** Shrink with cheap local steps first, and call the LLM last:

1. Read only the visible part of editors and long documents (macOS's visible-character-range attribute; to be verified per app).
2. Store only the **new lines** since the last snapshot of that window.
3. Group snapshots into **episodes**.
4. Run a cheap "anything worth remembering?" filter.
5. Gemini extracts a few structured memories per episode.
6. Raw observations expire after a few days, and memories stay.

**Expected result** (to be measured): about 20× fewer LLM input tokens and about 100× less long-term storage.
**Pitch line.** "Screens are mostly noise. I built a reduce-first pipeline so the LLM only sees what changed and matters, and nothing slow sits in the capture path."

## 2. Gmail's navigation drowned the email ✅

**Situation.** Every Gmail snapshot began with about 45 lines of chrome (Compose, the labels list, "Skip to content"…) before the email.
**What we tried.** We avoided Gmail-specific scraping, since it breaks whenever Gmail changes. Instead we dumped a **role histogram** of the live accessibility tree (`make dump`) and found that Gmail marks its regions with **ARIA landmarks** (Banner, Navigation, Search, Complementary, Main).
**What worked.** One generic rule: skip the non-content landmarks and keep Main. It works on any well-built website.
**Result.** A real Gmail thread went from 2,584 to 1,857 chars (−28%) and 125 to 80 lines, and the read got faster (68 → 55 ms).
**Tradeoff.** Gmail's message toolbar isn't tagged, so about 10 button labels remain.
**Pitch line.** "Instead of scraping one site, I used the accessibility semantics the web already publishes. One rule cleaned every well-built site."

## 3. Near-duplicate screens: three designs ✅

**Situation.** The app re-reads the screen every 5s. Most reads are the same screen with a changed unread badge or clock, and those shouldn't be stored again. A new chat message must be.
**Design 1, Jaccard similarity ≥ 0.9:** failed both ways. One badge change on a short screen scored 0.89, so it was stored. A new *"can you review my PR?"* in a long Slack channel scored **0.944**, so it was **dropped**, along with the commitment.
**Design 2, count of new word-triples:** fixed Slack, but "yep, will do" adds as many triples as a clock tick.
**Design 3, new lines after masking digits:** ✅ Accessibility text is one UI element per line, so a new message is always a new line, and a badge or clock never is once digits are masked.
**Result.** Both failure cases are kept as regression tests.
**Pitch line.** "Generic similarity measured the wrong thing. I picked a metric for *new information* that fits how the data is shaped."

## 4. The permission kept "forgetting" the app ✅

**Situation.** macOS stores the Accessibility grant against the app's **code signature**. An unsigned (ad-hoc) build gets a new identity every time you compile, so the toggle silently stops working.
**Twist.** Even after you created an Apple Development certificate, `security` reported "0 valid identities". Your certificate was issued by Apple's **WWDR G3** intermediate, while the keychain only had the expired 2023 one, so signing failed (`errSecInternalComponent`).
**What worked.** We read the certificate's issuer, downloaded Apple's public G3 intermediate, checked that it chains to Apple Root CA, and installed it. Now the app's *designated requirement* is "this bundle ID + this certificate", so the grant survives rebuilds (confirmed over 4+).
**Pitch line.** "I debugged TCC down to the certificate chain. On macOS, a permission belongs to a code-signing identity, not a file."

## 5. Chrome, Slack and Cursor returned almost no text ✅

**Situation.** Chromium and Electron apps don't build an accessibility tree unless an assistive app asks, because it's expensive.
**What worked.** We set `AXManualAccessibility = true` on each app (native apps ignore it). Cursor then gave full text in 62 ms.
**Pitch line.** "I know why screen-reading works in Notes but not Slack, and the one attribute that fixes it."

## 6. Real-app text was dirty ✅

**Situation.** Unit tests passed, but real apps produced:

- the Gmail draft *twice*, whole and again in fragments ("i wil", "submit"), because rich-text editors expose child spans as well as the value
- an invisible U+200E direction mark on every WhatsApp label
**What worked.** Once a text field returns its value, we don't read its children. Invisible direction and zero-width characters are stripped. Each fix has a test.
**Pitch line.** "Testing on real apps found four bugs the unit tests couldn't. Each one became a regression test."

## 7. A localhost API any web page could reach ✅

**Situation.** "It only listens on 127.0.0.1" isn't security. A web page can make your browser send requests to localhost, and with **DNS rebinding** it can read the replies.
**What worked.** Three layers: bind to 127.0.0.1 only, a random token in a `0600` file (a web page can't read it), and a Host-header allowlist (rebinding requests still say `Host: evil.example`). Tested: 401 without the token, 400 for a foreign Host.
**Pitch line.** "I treated the browser as an attacker's bridge into localhost and defended with a capability token plus Host checks."

## 8. Free API tier vs privacy ✅

**Situation.** We wanted Gemini's free tier. Its terms let Google use free-tier content to improve its products, with human review. Minimi's privacy promise relies on a *paid* plan.
**What worked.** Every observation records its `source`. Real screen captures are **stored locally and held back** from Gemini unless you're on the paid tier or explicitly opt in for test data. It's enforced in one function, tested, and shown in the menu.
**Pitch line.** "I turned a data-governance rule into a tested code path, not a line in the README."

## 9. Model output broke the UI ✅

**Situation.** A draft said `[[available times next week]]`, and the terminal UI library read `[available times next week]` as a style tag and hid it.
**What worked.** We escape all untrusted text (model output and screen text) where it's displayed, with a regression test. It's the same class of bug as XSS.
**Pitch line.** "LLM output is untrusted at *every* boundary, including rendering."

## 10. Failed LLM calls silently lost work ✅

**Situation.** Detection ran inside the insert loop. If Gemini failed (a 429), that observation was stored but never retried, because re-ingesting skipped it as a duplicate.
**What worked.** Store and process are separate steps. Processing state lives in the row, one transaction covers each observation, and failures are retried 3 times and then skipped (so there's no head-of-line blocking).
**Pitch line.** "Idempotent ingest plus resumable processing, so a rate limit never loses data."

## 11. Closing loops in many apps 🔵

**Situation.** The demo closes Gmail loops. A real product needs WhatsApp, Slack, docs, PDFs and research too.
**Proposal (ADR-026).** One planner agent plus **connectors** that expose typed tools, each tagged **read / draft / execute**. Approval depends on risk, not on the app: execute always needs a click. The flow is plan → approve → execute → verify, and the reply goes to the channel where the ask came from. The hands come from APIs, MCP servers, Mac automation (Shortcuts, URL schemes) or Accessibility actions for apps with no API (personal WhatsApp has none).
**Pitch line.** "Safety policy is keyed on what an action does, so adding an app is a new connector, not new safety code."

## 12. Detection missed meeting action items 🔵

**Situation.** "Sehaj: write the launch blog post draft by Oct 28" in meeting notes wasn't detected. Our prompt rule "tasks with no other person aren't loops" made it look like a to-do for yourself.
**Next.** Your prompt-iteration exercise: fix it without adding false positives, measured against the answer key.

## 13. Polling misses short-lived screens 🔵

**Situation.** The app reads the focused window every 5s. Anything shorter-lived (a toast, a 3-second glance) can be missed. Worse, the debounce only sends text that's unchanged on two reads in a row, so an email read for about 7s and then left is **never sent**: the first read is still settling when the app switch moves us on. (You found this by asking.)
**Why "poll faster" is wrong.** 1s polling means 5× more reads, nearly all identical. They're cheap (about 55 ms) and the line-novelty filter discards them, but that's wasted CPU and battery, and it still misses anything under 1s. Polling guesses *when* to look.
**Proposed.** Event-driven capture:
1. **AXObserver notifications:** value changed, focus changed, title changed, live-region changed (chat apps announce new messages). Wait about 1s after the last notification, then read once, at most once every 5s while you type continuously.
2. **Flush on leave:** when you switch app or window, send the pending snapshot immediately.
3. **A 30s backup poll** for apps that send poor notifications.

**Key insight.** Storage and LLM cost scale with **new lines**, not with how often we read (challenges #1 and #3). So reading at the right moments costs almost nothing. Time on screen also matters less than it seems: commitments persist (the thread is still there), and the Phase 5 Gmail connector can fetch the full source.
**Tradeoff.** Notification quality varies by app (native good, Electron mixed, canvas poor), so it has to be measured per app.
**Pitch line.** "I replaced guessing when to look with listening for changes, and decoupled read frequency from cost."

