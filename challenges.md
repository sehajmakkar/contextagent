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
| 19 | The loop eval said 100% because I wrote it *and* the prompt | 4 | ✅ held-out set |
| 20 | An inferred close hid a real deadline (NDA email ≠ contract renewal) | 4 | ✅ verifier |
| 21 | Dedupe judge called on almost everything (wrong threshold) | 4 | ✅ calibrated |
| 22 | A flaky loop that was really a contradiction in the spec | 4 | 🔵 your product decision |
| 23 | The agent eval said 10/10 while a draft committed the user to an 11-month lease | 5 | ✅ |
| 24 | No OAuth scope can stop sending, so "can't send" had to be architectural | 5 | ✅ |
| 25 | The "test" Gmail account was the main inbox | 5 | ✅ scoped mailbox |
| 26 | Parallel requests from the new UI crashed SQLite (thread affinity) | 6 | ✅ |
| 27 | Approve & Send did nothing in the live demo run | 6 | ✅ |
| 28 | Emailing people you never emailed, without opening an injection hole | 6 | ✅ |
| 29 | Detection died silently, and the brain kept smiling | 7 | ✅ |

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

## 19. The loop eval said 100%, because I wrote it *and* the prompt ✅

**Situation.** 43 labelled screens: precision, recall, due dates and closes all perfect.
**Why that's suspicious.** I wrote the prompt's "not a loop" list and the eval's tricky cases with the same categories in mind (self-reminders, Hinglish, group asks, injection). That's **leakage**: it measures how well the prompt matches its author's test, not how it generalises.
**What worked.** A **held-out set** of 16 harder cases the prompt never names: implicit commitments ("sounds good, I'll send slots tomorrow"), promises in quoted history, assignment on your behalf, "next Friday" said on a Friday, two commitments in one message, a close in a different app, an FYI forward. Scored once, never tuned on. Flash-Lite: precision **91%** (it fell for the FYI forward), recall 100%, due dates 8/8. 3.8 Flash: 100%.
**Also found.** The confidence-threshold sweep was flat: **LLM self-reported confidence is uncalibrated** (0.9+ even on its mistake).
**Pitch line.** "A perfect score on a test I wrote was evidence of leakage, so I built a held-out set and found the real failure mode."

## 20. An inferred close hid a real deadline ✅

**Situation.** End-to-end, Rahul's "merged!" correctly auto-closed the PR loop. But Jordan's *"Attached the signed NDA"* also closed **"Countersign the Contoso renewal (due Nov 15)"**: same person, different document. The deadline silently left the inbox.
**Why it's hard.** The analysis call sees a whole screen and several tracked loops at once, so "Jordan + signed" over-matched. It didn't even reproduce in the single-screen eval: model output varies between runs.
**What worked.** **Generator + verifier.** Every proposed close gets one narrow call that may only say yes for *this exact deliverable*. Contoso + NDA → false. Positive control (an NDA loop + the same email) → true. 0 real closes vetoed. Closes are rare, so the extra cost is negligible. The case is now a regression item in the eval.
**Pitch line.** "I gave the riskiest action its own verifier. Generation is broad, verification is narrow."

## 21. The dedupe judge ran on almost everything ✅

**Situation.** A full fixture run made **92 LLM calls for 33 episodes**, 26 of them judge calls.
**Why.** Loops are short imperative sentences ("Send X the Y"), so they cluster: **37 of 55 different-loop pairs** were under my 0.30 threshold.
**What worked.** Measured both sides. Paraphrases of the same loop: 0.022 / 0.041 / 0.105. Closest different loops: 0.164+. Threshold 0.14, with at most 2 judge calls. Calls dropped to 67.
**Pitch line.** "Every threshold in this system was set from measured positive and negative pairs, not picked."

## 22. A flaky loop that was really a spec contradiction 🔵

**Situation.** *"Confirm the launch date with marketing"* ← Priya appears in some full runs and not others.
**Root cause.** My prompt says "other people's meeting action items are not loops", but also defines they_owe as "owed to the user **or a group the user is in**". Priya's item is owed to the team you're in. The model resolves the contradiction differently on each run.
**Next.** A product decision: should "waiting on" items from meetings you attend be tracked as they_owe? (A dependency tracker, but noisier.)

## 23. 10/10, while a draft committed you to an 11-month lease ✅

**Situation.** The first agent eval passed 10/10, with the judge scoring every draft 5/5/5. Reading the drafts anyway turned up: *"Yes, I would like to renew the lease for another 11 months at the same rent."* The agent made a decision only you can make.
**Why the eval missed it.** The programmatic check wanted a `[[placeholder]]`, and there was one, used for "next steps". The judge's rubric asked about grounded / addresses the ask / tone, and the draft was grounded (the terms were in the thread). **Nothing asked about authority.** An eval only catches the failures its rubric names.
**What worked.**
1. A new judge dimension, `respects_authority`, plus forbidden decision phrases. The eval then failed 9/10, catching it.
2. An authority rule in the agent prompt: never accept, renew, agree to terms or pick times, and use a `[[placeholder]]` instead.
3. **Two grader bugs that surfaced next:** an over-broad forbidden phrase that matched neutral text, and a judge penalising the correct placeholder. Those were fixed in the grader, not the agent.
**Result.** 10/10 on three runs in a row. The report says plainly that the prompt was tuned on this eval.
**Follow-up (ADR-054).** With 12 scenarios and a longer prompt, the lease overstep came back in 2 of 3 runs. So the rule moved into code, as an authority verifier before any draft is saved. It over-blocked once ("confirm 2:30" *is* the owed task) and was narrowed to "decisions beyond what's owed". Fresh run on 2026-10-26: **12/12**, and the lease draft was blocked once and then rewritten with a placeholder.
**Pitch line.** "My agent eval passed while a draft was signing the user up for a lease. I read the outputs, found the rubric had no 'authority' axis, and fixed the eval before the agent."

## 24. No OAuth scope can stop sending ✅

**Situation.** The design needs "the model can draft, but only you can send."
**Why it's hard.** Gmail's `gmail.compose` scope covers drafts **and** sending, and there's no drafts-only scope. A permissions-only design can't express the rule.
**What worked.** Make it architectural and test it:
1. `send` isn't a model tool (the registry asserts there are no `execute` tools).
2. Only the approval endpoint calls `send_draft`.
3. It requires the hash of the draft you saw, claims the run atomically (it can't send twice), and verifies the message is in Sent before closing the loop.

Tests cover a stale hash (refused), a double approve (sent once), an edited body (what you edited is sent), and an injected recipient (refused in code even when the model complies).
**Pitch line.** "When the permission system couldn't express 'draft but don't send', I enforced it in the architecture and proved it with tests."

## 25. The "test" Gmail account was the main inbox ✅

**Situation.** For the live test, the connected account turned out to be your primary inbox (about 8,800 emails), and inference runs on Gemini's free tier, which may use what it's sent (ADR-014).
**Why it's hard.** The agent decides its own searches, and `gmail.readonly` exposes the whole mailbox. "Be careful" in a prompt isn't a control.
**What worked.** A **scoped mailbox**: every search gets `subject:"[CA-TEST]"` appended, only threads from scoped searches can be opened or replied in, and the free tier refuses an unscoped real mailbox. Then a synthetic `[CA-TEST]` thread was seeded for the test.
**Result (live, real Gmail):** the agent found the seed thread, drafted with **63.6% / 58.9%** from memory (4 LLM calls, 7.4 s). Gmail independently confirmed the draft (same thread, `In-Reply-To` set). Approve → **sent, verified in Sent, loop closed**, and a double approve was refused. A second thread tested the authority rule (`[[Yes, I am renewing / No…]]`) and **reject → Gmail 404, nothing sent, loop reopened**.
**Pitch line.** "I tested a live email agent on my real inbox without exposing my real email, by enforcing least privilege at the query level."

## 26. Parallel requests from the new UI crashed SQLite ✅

**Situation.** The first live run of the Phase 6 app: `GET /memories → 500`, `GET /status → 500`, with `sqlite3.ProgrammingError: SQLite objects created in a thread can only be used in that same thread`. 60 tests had passed.
**Why.** The app refreshes `/loops`, `/memories` and `/status` **in parallel** (`async let`). FastAPI runs a sync `yield` dependency's setup, the endpoint and the teardown on its thread pool, and with overlapping requests those land on **different threads**. Python's `sqlite3` refuses cross-thread use by default. Sequential tests never overlapped, so the pool happened to reuse one thread.
**What worked.** First a test that reproduces it (24 concurrent requests, which **failed**), then `check_same_thread=False` for request-scoped connections. That's safe because each connection still belongs to one request and is never used concurrently. The same review found a second latent issue: a cached Gmail client shared across requests, and `httplib2` isn't thread-safe, so it's now one connection per run.
**Result.** The test passes, and live: `/loops`, `/memories`, `/status` all 200, 0 tracebacks.
**Pitch line.** "The new UI's parallel requests exposed a thread-affinity bug that sequential tests couldn't. I reproduced it in a test before fixing it."

## 27. Approve & Send did nothing in the live demo run ✅

**Situation.** Your first real run: the loop was detected, the agent drafted, you edited the draft, and Approve & Send and Reject did nothing.
**Root cause, a chain of three.**
1. You edited the body, so approval first updates the Gmail draft through the **scoped** mailbox.
2. In Phase 6 I'd switched to a fresh mailbox per request (for thread safety), and the scoped mailbox only allowed threads *its own* searches had returned. The approval request's fresh one had never searched, so it refused the agent's own thread and the run became `failed`.
3. Every later click then got 409, and the **UI's 3-second refresh wiped the error message**, so the buttons looked dead.
**Found by** the brain's request log (`POST /actions/1/approve → 409`) plus the stored error on the run. Each fix was right on its own; the bug was how they combined.
**Fixed.** Scopes removed (ADR-052). A failed send now **releases its claim** back to `awaiting_approval` with the error kept, so you can retry (regression test with a flaky send). Run errors live on the card itself, so a refresh can't erase them. The stray Gmail draft was cleaned up.
**Pitch line.** "Two individually correct changes, a per-request client and a visibility-scoped wrapper, combined into a dead button. Request logs and stored errors found it, and failures are now retryable and can't be hidden by a refresh."

## 28. Emailing people you never emailed, without opening an injection hole ✅

**Situation (your idea).** "I'll mail you this" happens on WhatsApp and in Notes, where there's no thread to reply in. So: find a thread, and if there isn't one, write a new email.
**Why it's hard.** "Recipients ⊆ thread participants" was the core prompt-injection defence. With no thread, the model could be talked into any address ("also send this to x@evil.com").
**What worked.** Move who chooses the recipient. The model may only use the loop's known contact address, or leave To blank. Only you can type another address, in the UI, and only you can send. Approve stays disabled without a valid recipient. Tests: an injected recipient is refused, an empty To blocks sending, a reply's recipients stay pinned, a malformed address is rejected.
**The eval found a second risk:** a same-named "Arjun Rao" at a *different* address had a thread on the same topic, and the agent replied there, possibly to the wrong person. That led to the right-person rule: when the loop knows the address, a thread must contain it.
**Then it got flaky:** a longer prompt made Flash-Lite follow rules less reliably (lease overstep 2/3 runs, wrong person 1/3). Both moved into code: a deterministic right-person check and an **authority verifier** that refuses to save a draft that decides for you (ADR-054).
**Pitch line.** "When a new feature removed my injection guard, I moved recipient choice to the human. When prompt rules started flaking in the eval, I moved them into code: a deterministic check and a narrow verifier."

## 29. Detection died silently, and the brain kept smiling ✅

**Situation.** The day before the shoot, loops from Notes appeared late or never. `/status` said `ok: true`, captures were accepted, and 4 episodes sat waiting.
**Why it was hard.** Nothing looked broken. The API thread was healthy. Only the background worker was dead, and the one signal (`auto_detect_running: false`) wasn't shown anywhere in the UI.
**Root cause.** The worker caught model errors but not database errors. "Delete all data" removed the episode the worker was processing, saving its memories hit a foreign-key error, and the exception ended the thread for good. A second, smaller delay came from Notes: its window title changes with the note count, so the visit you left never got an end-of-visit and waited 5 minutes (ADR-056).
**What worked.** A supervisor loop: any unexpected error is logged, charged to that episode (so a poison episode is dropped after 3 tries), and the loop continues. The panel shows a red banner if detection ever stops. Reading a new window closes the previous visit, and the newest visit is processed first. There's a test that injects a sqlite error and checks the worker carries on.
**Pitch line.** "Background workers fail quietly. I made mine unkillable, gave a poison episode a retry budget, and made 'detection stopped' visible to the user instead of hiding it in a status field."

