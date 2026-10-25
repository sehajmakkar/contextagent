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
| 13 | Polling misses short-lived screens, and faster polling just makes duplicates | 2 → 3 | ✅ event-driven |
| 14 | Chat history off-screen still came through (Chromium clamps hidden elements) | 3 | ✅ |
| 15 | Two macOS timing races in event-driven capture | 3 | ✅ |
| 16 | Free tier: 20 requests/day, and retries that made it worse | 3 | ✅ fail-fast + Flash-Lite |
| 17 | Duplicate detection merged two different facts (Q2 vs Q3) | 3 | ✅ |
| 18 | An eval that said 100%: ceiling effects and RRF's blind spot | 3 | ✅ measured, documented |

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

## 13. Polling misses short-lived screens ✅ (built in Phase 3)

**Situation.** The app reads the focused window every 5s. Anything shorter-lived (a toast, a 3-second glance) can be missed. Worse, the debounce only sends text that's unchanged on two reads in a row, so an email read for about 7s and then left is **never sent**: the first read is still settling when the app switch moves us on. (You found this by asking.)
**Why "poll faster" is wrong.** 1s polling means 5× more reads, nearly all identical. They're cheap (about 55 ms) and the line-novelty filter discards them, but that's wasted CPU and battery, and it still misses anything under 1s. Polling guesses *when* to look.
**Proposed.** Event-driven capture:
1. **AXObserver notifications:** value changed, focus changed, title changed, live-region changed (chat apps announce new messages). Wait about 1s after the last notification, then read once, at most once every 5s while you type continuously.
2. **Flush on leave:** when you switch app or window, send the pending snapshot immediately.
3. **A 30s backup poll** for apps that send poor notifications.

**Key insight.** Storage and LLM cost scale with **new lines**, not with how often we read (challenges #1 and #3). So reading at the right moments costs almost nothing. Time on screen also matters less than it seems: commitments persist (the thread is still there), and the Phase 5 Gmail connector can fetch the full source.
**Tradeoff.** Notification quality varies by app (native good, Electron mixed, canvas poor), so it has to be measured per app.
**Pitch line.** "I replaced guessing when to look with listening for changes, and decoupled read frequency from cost."
**Built (ADR-032).** Measured: a 2-second glance at a TextEdit file was captured `settled` about 1s after opening. Switching away triggered a `leaving` read that correctly found nothing new.

## 14. Off-screen chat history still came through ✅

**Situation.** Cursor gave 20,000 chars (the cap). I assumed one huge file value, but a role histogram showed **338 `AXDocumentArticle` elements**: the chat panel's whole scroll history, kept in the DOM.
**First try.** Skip elements whose frame doesn't intersect the window. It worked in Notes (3,885 → 1,183 chars) but did **nothing** in Cursor.
**Why.** A probe printed the frames. Chromium **clamps** scrolled-away elements to the edge of the scroll area as a **1pt sliver** (`y=143, height=1`), which technically intersects the window.
**What worked.** Also treat any frame thinner than 2pt on one side as hidden (nothing readable fits in 1pt), while 0×0 still means "unknown". Cursor: 400 subtrees skipped, no longer capped.
**Pitch line.** "I measured the frames instead of trusting the docs, and found Chromium reports hidden elements as 1-point slivers."

## 15. Two macOS timing races ✅

**Situation.** The scripted test ("open file A, glance at file C for 2s, switch to Finder") missed file A.
**How we found it.** We added `os.Logger` tracing (IDs and counts only, never text) and read it with `/usr/bin/log`. zsh's `log` builtin shadows Apple's tool, which was a gotcha of its own.
**Race 1.** macOS sends the old app's *deactivated* **after** the new app's *activated*. Our leave handler cancelled "the" scheduled read, which by then belonged to the new app.
**Race 2.** A just-launched app rejects notification registration (`observing=0`), and its first read finds no window yet.
**What worked.** Don't cancel on deactivate (the settled read always targets the frontmost app). Retry registration on each read. Retry a no-window read up to 3 times. Result: A captured 1s after launch, C 1s after opening.
**Pitch line.** "Tracing showed macOS delivers activation events out of the order you'd assume. The fix was to make each handler independent of that order."

## 16. Free tier: 20 requests a day, and retries that made it worse ✅

**Situation.** The first full fixture run died at episode 7: `generate_content_free_tier_requests, limit: 20, model: gemini-3.8-flash`, "retry in 9h56m". The SDK had retried each daily-quota 429 five times with backoff, wasting about 40s per episode and using up each episode's 3 attempts.
**What worked.** Parse Google's 429 body ourselves. `QuotaFailure.quotaId …PerDay…` → stop the batch at once and don't charge the episode. A per-minute limit → wait the server's `RetryInfo` delay plus jitter.
**Resolved (your call).** Flash-Lite for testing and evals (ADR-039), which has its own quota. It ran the whole fixture pipeline (66 calls) without hitting a limit.
**Pitch line.** "Retry policy should depend on *why* you're limited: per-minute means wait, per-day means stop."

## 17. Duplicate detection merged two different facts ✅

**Situation.** Revisiting a thread re-extracts the same memory ("Sehaj will send Priya the Q3 numbers…"), so we fold near-identical vectors into one.
**Calibration first.** Instead of guessing a threshold, we measured pair distances. A true restatement was 0.062, while two *different* lease facts were 0.094, and the median pair was 0.315. My placeholder of 0.10 would have merged the lease facts and lost a deadline. So: 0.075 plus the same kind.
**It still failed in the eval.** *"Q2 blended M1 retention 58.9%, up from 55.4%"* was folded into *"Q3 … 63.6%, up from 58.9%"*: same kind, nearly the same sentence. **Embeddings blur exact tokens** (Q2/Q3, 58.9/63.6), the weakness we wrote about in the very first primer.
**What worked.** A duplicate must also agree on its numbers: one memory's number set is contained in the other's. A restatement may add a resolved date ({3} ⊂ {3, 21, 2026}), but different figures never pass. Duplicates are *marked*, never deleted, so mistakes can be undone. The Q2 query became answerable.
**Pitch line.** "I calibrated the dedupe threshold on real distances, then caught a false merge in the eval. Vectors blur numbers, so I added an exact-token check."

## 18. An eval that said 100% ✅

**Situation.** The first retrieval eval gave every mode **100% Recall@5**.
**Why that's a red flag.** With 48 memories, the top 5 is about 10% of everything: a **ceiling effect**. A metric that can't fail tells you nothing.
**What we did.** Added Recall@1 and MRR, separated **extraction misses** (no memory existed) from retrieval misses, and looked at per-query ranks. Recall@1: vector 90% = hybrid 90% > BM25 84% > hybrid+recency 81%. Per-query ranks showed the textbook pattern: BM25 wins exact tokens (`PR #519`), vectors win paraphrases ("current price of Pro"), and RRF demotes results only one retriever finds ("cohort chart": vector 3 → hybrid 6).
**Honesty.** The differences are 1–3 queries out of 31, so we chose hybrid for robustness (exact IDs, offline BM25) and didn't tune weights on a set that small.
**Pitch line.** "When my eval said 100%, I made it harder rather than trusting it, and I can tell you which queries each retriever wins and why."

