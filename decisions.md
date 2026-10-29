# Decisions (ADRs)

Every real technical or product decision goes here as a short **Architecture Decision Record**. In an interview, "why X over Y?" should be answerable straight from this file.

Statuses: **Proposed** (Claude recommends it, waiting on you) · **Accepted** · **Superseded by ADR-N** · **Revisit**

Superseded ADRs stay in the file. How a decision changed, and why, is part of the story.

### Template

```
## ADR-NNN: Title
Status · Date · Phase
Context: what problem, what constraints
Options: A / B / C (one line each)
Decision: what we chose
Tradeoffs: what we give up, and the risks
Revisit when: the signal that would change our mind
Interview angle: the one-sentence answer to "why?"
```

### Index

| # | Decision | Status |
|---|---|---|
| 001 | The wedge is an action agent that closes loops, with a human approving | **Accepted** |
| 002 | Prototype, not product | **Accepted** |
| 003 | Walking skeleton first | **Accepted** |
| 004 | Swift app plus a Python brain on localhost | **Accepted** |
| 005 | Accessibility API only, never screenshots | **Accepted** |
| 006 | ~~Claude as the LLM~~ | Superseded by 019 |
| 007 | SQLite + FTS5 + sqlite-vec in one local file | **Accepted** |
| 008 | ~~Local fastembed embeddings~~ | Superseded by 020 |
| 009 | Hybrid retrieval with RRF, chosen by eval | **Accepted** |
| 010 | Structured outputs with Pydantic everywhere | **Accepted** |
| 011 | Hand-written agent loop, no framework | **Accepted** |
| 012 | Drafts by default, sending needs a human click | **Accepted** |
| 013 | Gmail API directly | **Accepted** |
| 014 | Privacy model: local storage, minimal egress, honest disclosure | **Accepted** |
| 015 | Small hand-labeled evals from day one | **Accepted** |
| 016 | MCP in v2 | **Accepted** |
| 017 | Python tooling: uv, FastAPI, Pydantic, pytest | **Accepted** |
| 018 | Runs on a reviewer's Mac: Docker brain, native app, demo mode | **Superseded** by 055 (the Docker part) |
| 019 | Gemini as the LLM through the official `google-genai` SDK | **Accepted** |
| 020 | Gemini embeddings (`gemini-embedding-2`, 768 dimensions), stored locally | **Accepted** |
| 021 | Call Gemini through `models.generate_content` (stateless), not the Interactions API | **Accepted** |
| 022 | Plain `sqlite3` with hand-written SQL and `user_version` migrations, no ORM | **Accepted** |
| 023 | CLI with Typer + Rich | **Accepted** |
| 024 | Real first: demo mode, fake mailbox, Docker, and recorded responses move to Phase 7 | **Accepted**, Docker part superseded by 055 |
| 025 | Loop detection v0: one call per observation, confidence ≥ 0.6, grounding check, exact-quote dedupe | **Accepted** |
| 026 | Actions are risk-classed tools behind connectors, with approval keyed on risk | Proposed (Phase 5) |
| 027 | ~~Live captures stay local on the free tier~~ | Superseded by 052 |
| 028 | Swift Package + Makefile bundling instead of an `.xcodeproj` | **Accepted** |
| 029 | Local API auth: 0600 token file + Host-header allowlist + 127.0.0.1 bind | **Accepted** |
| 030 | Capture triggers and dedupe: app switch + 5s poll, two-read debounce, masked line novelty | **Accepted** |
| 031 | How we read the AX tree: web area first, AXManualAccessibility, skip secure fields, batched reads, caps | **Accepted** |
| 032 | Event-driven capture: AXObserver + coalescer, flush on leave, 30s backup poll | **Accepted** |
| 033 | Episodes: one visit to one window, lines merged, processed once when closed | **Accepted** |
| 034 | One memory-extraction call per episode, structured, grounded, with provenance | **Accepted** |
| 035 | Retention: raw snapshot text erased after 7 days once processed | **Accepted** |
| 036 | Visibility culling: skip off-screen and Chromium-clamped elements | **Accepted** |
| 037 | Handle 429s ourselves: per-minute → wait the server's delay; per-day → stop the batch | **Accepted** |
| 038 | Retrieval default: hybrid RRF (BM25 + vectors), recency off; duplicates need same kind + nested numbers | **Accepted** |
| 039 | Flash-Lite (`gemini-3.5-flash-lite`) for testing and evals | **Accepted** |
| 040 | Loop lifecycle: explicit state machine + transition log; table rebuild with FKs off | **Accepted** |
| 041 | Loop analysis v2: one call finds new loops and updates tracked ones; self-reminders; semantic dedupe with a judge | **Accepted** |
| 042 | Model per stage (free tier): Flash-Lite everywhere; 3.8 Flash is the measured upgrade for loop analysis | **Accepted** |
| 043 | Generator + verifier for closes; judge threshold calibrated at 0.14 | **Accepted** |
| 044 | Gmail via google-api-python-client; scopes readonly + compose; OAuth token in the macOS Keychain | **Accepted** |
| 045 | The agent: hand-written loop, provider-neutral tool types, risk-classed tools with guardrails in code, no send tool | **Accepted** |
| 046 | Approval protocol: approve the hash you saw, claim-once, send, then verify in Sent before closing | **Accepted** |
| 047 | FakeMailbox pulled forward from Phase 7 for tests and agent evals | **Accepted** (amends 024) |
| 048 | ~~Scoped mailbox~~ | Superseded by 052 |
| 049 | Agent progress over Server-Sent Events (SSE) | **Accepted** |
| 050 | Inbox UI: Minimi-style panel + dashboard + settings; trust guards in the UI | **Accepted** |
| 051 | Demo-ready flow: end the visit when you leave the window (the live-scope part superseded by 052) | **Accepted** |
| 052 | Your call: remove the free-tier gating and both scopes; every capture is processed | **Accepted** · supersedes 027, 048, part of 051 |
| 053 | No thread → a new email; recipients come only from the loop's known contact or from you | **Accepted** · amends 012, 045 |
| 054 | Prompt rules that kept flaking became code: authority verifier + right-person check | **Accepted** |
| 055 | No Docker: the reviewer runs the brain with `uv` and the app with `make` | **Accepted** · supersedes the Docker part of 018 / 024 |
| 056 | Reading a window closes every other open visit; the newest visit is processed first | **Accepted** · extends 051 |

---

## ADR-001: Our wedge is an action agent that closes loops, with a human approving

**Accepted** · 2026-10-24 · Phase 0

**Context.** Minimi's public site (read 2026-10-24) describes capture through Apple's accessibility infrastructure, local memory, an MCP connector, and an "Open loops Inbox" that *finds* loops and "resolves closed loops" when it sees they're done. It doesn't describe the app taking outward actions like sending an email for you. A prototype that copies Minimi proves nothing. One that adds the obvious next step shows product sense.
**Options.** (A) Clone Minimi more cheaply. (B) Better memory accuracy. (C) **Act on loops**: draft, approve, send, verify, close.
**Decision.** C, with Gmail replies as the first and only action.
**Tradeoffs.** Actions add risk (wrong recipient, prompt injection) and need OAuth. We reduce that with drafts-first plus human approval (ADR-012). We spend less time on capture breadth and memory quality.
**Revisit when.** Minimi ships actions themselves. Then pitch a different action, such as calendar or Slack.
**Interview angle.** "Finding a loop is half the value. Closing it is where time is saved, but only if the user stays in control of anything that leaves their machine."

## ADR-002: Build a prototype, not a product

**Accepted** · 2026-10-24 · Phase 0

**Context.** The goal is an interview, plus learning. Time spent on production concerns doesn't show up in a 3-minute demo.
**Decision.** Single user, Apple Silicon, English, Gmail only, local only, unsigned dev build. No accounts, billing, sync, or App Store sandbox. It still has to run cleanly on a reviewer's Mac (ADR-018).
**Tradeoffs.** It isn't something you'd hand to the general public. The demo is a video, plus a repo that runs.
**Interview angle.** "I scoped hard to the riskiest, most differentiating path and wrote down what I cut."

## ADR-003: Walking skeleton first

**Accepted** · 2026-10-24 · Phase 1

**Context.** The risky part is the agent at the end of the pipeline. Building capture perfectly first could use up all the time before the differentiator exists.
**Options.** (A) Build each layer to completion in order. (B) **Thin end-to-end version first**, then deepen each stage.
**Decision.** B. Phase 1 goes from fixtures to loops to a drafted email in a CLI.
**Tradeoffs.** Some throwaway code. Early prompts are tuned on synthetic data.
**Interview angle.** "De-risk integration early, then replace each stub with the real thing."

## ADR-004: A native Swift shell plus a Python "brain" on localhost, with the brain owning the DB

**Accepted** · 2026-10-24 · Phase 0

**Context.** Capture needs native macOS APIs (Accessibility). The AI work (LLM SDK, embeddings, evals) is easiest and most transferable in Python, which is what AI engineering interviews assume.
**Options.**

- (A) All Swift. Native, but a weaker AI and eval ecosystem.
- (B) Electron/TypeScript. One language, but AX access needs native modules and the app would be heavier.
- (C) **Swift for capture and UI, Python for the brain**, talking over HTTP on 127.0.0.1.
**Decision.** C. The brain is the only process that touches SQLite. Swift sends observations and reads loops over HTTP. How reviewers run it is in ADR-018.
**Tradeoffs.** Two languages and two processes to run. Local HTTP needs a shared-secret header so other local apps can't call it. In exchange, each side can be tested on its own, and the brain can run headless or in Docker against fixtures.
**Revisit when.** Shipping for real. Then you'd bundle the brain as a signed sidecar binary inside the `.app`.
**Interview angle.** "Native where the OS requires it, Python where the AI tooling lives, and one owner for the data."

## ADR-005: Capture through the Accessibility API only, never screenshots

**Accepted** · 2026-10-24 · Phase 2

**Context.** Minimi's FAQ says it reads screen content "via Apple's accessibility infrastructure" and doesn't take screenshots. You decided screenshots are too invasive.
**Options.** (A) Screenshots with OCR (ScreenCaptureKit + Vision). Works for any app, but it captures every pixel, including things you didn't mean to share, and it costs more CPU. (B) **Accessibility tree text.** It's already text with structure (roles, titles, values), cheap, and has no images.
**Decision.** B only. No Screen Recording permission, no pixels, and no OCR fallback. If an app exposes no useful AX text, we skip it and record that in `docs/capture-coverage.md`.
**Tradeoffs.** Needs the Accessibility permission, which is powerful, so we explain it on first run. Electron and canvas apps vary in how much text they expose. Some apps will have gaps, and we accept that. Sandboxed (App Store) apps can't read other apps' AX trees, which is fine under ADR-002.  
**Interview angle.** "Text from the AX tree gives better signal, costs less, and never touches pixels. Privacy is enforced by the architecture, not by a policy promise."

## ADR-006: Claude as the LLM

**Superseded by ADR-019** · 2026-10-24

The original proposal was the Anthropic SDK with `claude-opus-5-5`. We replaced it because Claude has no free API tier, and Gemini's free tier makes the prototype free to build and free for reviewers to run. What carried over into ADR-019: a thin `llm/client.py` interface, and picking the model for each pipeline stage from eval numbers.

## ADR-007: Storage is SQLite (WAL) + FTS5 + sqlite-vec in one file on the Mac

**Accepted** · 2026-10-24 · Phase 1/3

**Options.** (A) Postgres + pgvector, which means running a server. (B) Chroma or LanceDB, a separate store from the relational data. (C) **SQLite with extensions.**
**Decision.** C. One local file holds relational data, keyword search, and vectors (768 dimensions, ADR-020). It lives at `~/Library/Application Support/ContextAgent/brain.db`, and in Docker that folder is bind-mounted (ADR-018). Deleting everything is one folder. Nothing extra has to run.
**Tradeoffs.** sqlite-vec does brute-force or simple index search, which is fine up to roughly 100k vectors (our demo has hundreds). There's a single writer, which is fine because the brain is the only writer. Check that sqlite-vec has a linux/arm64 wheel for the Docker image.
**Interview angle.** "Local-first means the database ships inside the app. SQLite is the standard choice for that."

## ADR-008: Local embeddings with fastembed

**Superseded by ADR-020** · 2026-10-24

The original proposal was on-device embeddings (bge-small, 384 dimensions) so memory text would never leave the Mac. We replaced it to follow Minimi's approach (Gemini embeddings) for better quality and no model download. fastembed stays as a possible **offline/strict-privacy mode** in Phase 8, behind the same `embed()` interface.

## ADR-009: Hybrid retrieval (BM25 + vectors) with Reciprocal Rank Fusion, chosen by eval

**Accepted** · 2026-10-24 · Phase 3

**Context.** Queries mix exact tokens ("Q3", "Priya") with fuzzy meaning ("the retention stuff").
**Decision.** Implement BM25, vector, and hybrid (RRF, k=60) with recency weighting. Ship whichever wins Recall@5 and MRR on our eval set.
**Tradeoffs.** More moving parts than a single method. RRF ignores raw score sizes, which is a feature, since BM25 and cosine scores aren't comparable. BM25 runs fully offline, so if the Gemini API is down or rate-limited, keyword search still works.
**Interview angle.** "Keyword search catches names and numbers, vectors catch paraphrases, and RRF combines them without having to calibrate scores."

## ADR-010: Every LLM extraction uses structured outputs with a Pydantic model

**Accepted** · 2026-10-24 · Phase 1

**Decision.** Define the output as a Pydantic model and pass its JSON Schema to Gemini as the response format (`mime_type: application/json` plus the schema). Then validate with `Model.model_validate_json(...)`. Never regex-parse free text. Use this for loop candidates, memories, and judge verdicts.
**Tradeoffs.** The schema has to be designed carefully, since too many required fields leads to invented values. So include `confidence` and a nullable `due_at`. We validate even though the API constrains the output, because schema support has limits and the check costs nothing.
**Interview angle.** "The output schema is the contract between the LLM and the rest of the system, and I still validate at the boundary."

## ADR-011: A hand-written agent loop, with no agent framework or SDK auto-calling

**Accepted** · 2026-10-24 · Phase 5

**Options.** (A) LangChain, LangGraph, CrewAI, or Google ADK. (B) The SDK's automatic function calling, where it runs your Python functions for you. (C) **A manual loop**: send tools, read the `function_call` steps, run them ourselves, send back the `function_result`s, and repeat.
**Decision.** C. We own the loop, so we can enforce the step limit, the allowlist, the approval gate, and the audit log at each call. Gemini thinking models return thought blocks or signatures that must be passed back unchanged in stateless mode. Learning that is part of the exercise.
**Tradeoffs.** More code to own. In return, you'll understand every step, which is what interviewers probe, and our guardrails sit *in* the loop instead of wrapped around a black box.
**Interview angle.** "I can explain the agent loop without a framework, and our safety checks live inside it."

## ADR-012: Drafts by default, sending needs a human click, and all tool content is untrusted

**Accepted** · 2026-10-24 · Phase 5

**Context.** The agent reads untrusted text (screen content and emails), has access to private data (memory), and can communicate outward (email). That combination is the classic setup for prompt injection to exfiltrate data.
**Decision.** The model can only create drafts. `send` isn't a model tool, so only the approval endpoint calls it. Recipients must already be in the thread. Untrusted content is delimited and labeled as data. The agent has a step and token budget, and every action is written to the audit log. A prompt-injection regression test is required.
**Tradeoffs.** It's less "magical" than full autonomy. That's intended: it makes for a better trust story than an agent that sends on its own.
**Interview angle.** "Break the injection chain by removing autonomous outward communication, not by hoping the prompt holds."

## ADR-013: Call the Gmail API directly, with a fake mailbox for demo mode

**Accepted** · 2026-10-24 · Phase 5

**Options.** (A) **Gmail API with Google's Python client.** (B) An integration platform such as Composio. (C) A Gmail MCP server.
**Decision.** A, behind a `Mailbox` interface with two implementations: `GmailMailbox` (real OAuth) and `FakeMailbox` (a local JSON inbox seeded from fixtures, for demo mode and tests; ADR-018).
**Tradeoffs.** Hand-written auth and token refresh. It won't scale to many integrations. Mention B and C as the path to scaling.
**Interview angle.** "Do one integration deeply, put it behind an interface, and fake it for tests and demos."

## ADR-014: Privacy model with local storage, minimal egress, and honest disclosure

**Accepted** · 2026-10-24 · Phase 2

**Context.** We follow Minimi's model: everything is **stored** on the Mac, and **inference** (embeddings and the LLM) goes to Gemini over TLS. One catch: **the free tier and the paid tier handle data differently.** Google's Gemini API terms (checked 2026-10-24):

- **Free (unpaid):** content may be used "to provide, improve, and develop Google products", and "human reviewers may read, annotate, and process" it. The terms say: "Do not submit sensitive, confidential, or personal information to the Unpaid Services."
- **Paid** (a Cloud project with active billing): content isn't used to improve products, and it's logged briefly only for abuse detection. Minimi's "on a paid plan… Google doesn't train on or retain this data" refers to this tier.

**Decision.**

1. Everything persistent stays local (ADR-007). We store no data in any cloud service.
2. Redact before storing *and* before any API call. Send only the snippets a step needs.
3. **Free tier is for synthetic and test data only.** Demo mode, fixtures, and the dedicated test Gmail account are all fake, so the free tier is fine there. Live capture of your real screen is meant to use a paid key. The brain reads `GEMINI_TIER=free|paid` and shows a clear warning banner in the app when live capture is on with a free key.
4. Use stateless API calls. We don't ask Gemini to store conversation state on its side (ADR-019).
5. Settings and the README say exactly what leaves the device, and when.
6. At rest: FileVault plus `0600` file permissions for now. Evaluate DB-level encryption (SQLCipher, with the key in Keychain) in Phase 7, after checking that it works with sqlite-vec.

**Tradeoffs.** It's not fully offline. Phase 8's local-model and local-embedding mode is the answer to that. Being honest about the free tier makes the pitch slightly less impressive but far more credible.
**Interview angle.** "Local-first is about where data lives and who controls it. I can tell you exactly which bytes leave the machine, on which tier, and why."

## ADR-015: Small hand-labeled evals from day one

**Accepted** · 2026-10-24 · Phase 3–5

**Decision.** Three small eval sets: retrieval (about 30 queries), loops (about 40 snippets), and agent tasks (about 10). Each has a runnable script and saved results. Re-run them after every prompt or model change. To fit within free-tier rate limits, cache embeddings and LLM responses keyed by (model, prompt hash).
**Tradeoffs.** Small samples are noisy, so report counts as well as percentages. It's labelling work, but it's also the best interview material you'll have.
**Interview angle.** "Without evals, prompt changes are guesswork. I can show what each change did to the numbers."

## ADR-016: Push MCP to v2

**Accepted** · 2026-10-24 · Phase 8

**Context.** Minimi already ships a memory MCP, so it's not our differentiator. The readme already marks MCP as v2.
**Decision.** Build it after the demo works, as a thin layer over existing functions.
**Interview angle.** "MCP is an interface over the core. The core value is loops and actions."

## ADR-017: Python tooling is uv, FastAPI, Pydantic v2, and pytest

**Accepted** · 2026-10-24 · Phase 0

**Decision.** `uv` for environments and the lockfile (`uv.lock`), which the Docker image also builds from, so dev and Docker get identical dependencies. FastAPI because it's typed, builds on Pydantic, and makes SSE streaming easy. pytest for tests.
**Tradeoffs.** None worth noting. These are the defaults in modern Python AI work.

## ADR-018: Runs on a reviewer's Mac with a Docker brain, a native app, and demo mode

**Accepted** (amended by ADR-024) · 2026-10-24 · Phase 1 onward

**Context.** You'll send the GitHub repo to companies. A reviewer should go from `git clone` to a working demo in minutes, without installing a Python toolchain, without creating Google OAuth credentials, and ideally without granting powerful permissions to an unknown app.
**Key constraint.** Docker on macOS runs a **Linux VM**. Code inside a container can't call macOS APIs, so it can't read the Accessibility tree or show a menu-bar UI. Docker can run the **brain** but not the **app**.
**Options.**

- (A) Docker for everything. Impossible for the app.
- (B) Native only (uv and Xcode). Reviewers need a matching toolchain.
- (C) **Docker for the brain, native for the app, plus a demo mode that needs neither real capture nor real Gmail.**
**Decision.** C.
- `docker compose up` builds the brain from the same `uv.lock` and maps the port **only to localhost** (`127.0.0.1:8765:8765`, so it isn't exposed on the network). Data goes to a bind-mounted folder on the Mac, not inside the container.
- The app runs from `make app` (`xcodebuild`), or from a prebuilt `.app` attached to a GitHub Release. It's ad-hoc signed, so the README explains right-click → Open.
- `DEMO_MODE=1` replays fixture "screen sessions" in place of live capture and uses `FakeMailbox` in place of Gmail. A reviewer needs **one thing: a free Gemini API key**. Since the data is synthetic, the free tier is fine (ADR-014).
- There's a headless path too: `docker compose run brain demo` prints the whole flow (loops detected, agent steps, draft) in the terminal. It works on any OS, even without the Mac app.
- For your own development, `uv run` natively is faster. Both paths share one lockfile.
- CI (GitHub Actions) builds the image and runs the tests against **recorded LLM responses**, so CI needs no API key and the README can show a green badge.
**Tradeoffs.** Docker adds a little complexity (Dockerfile, compose file, volume paths) and a slower first start. The reviewer still has to run the native app separately. Recorded responses can drift from live model behaviour, so re-record them when prompts change.
**Revisit when.** Shipping for real. Then you'd bundle the brain inside the signed `.app` and drop Docker.
**Interview angle.** "I designed it so you can run the demo in two commands with zero credentials beyond a free key, and I know exactly why the Mac half can't be containerized."

## ADR-019: Gemini as the LLM, through the official `google-genai` Python SDK

**Accepted** · 2026-10-24 · Phase 1 (model per stage settled in Phase 4)

**Context.** It has to be free to build and free for reviewers to run. Gemini's Flash models have a free tier, and Minimi also uses Gemini.
**Options.** (A) **The official** `google-genai` **SDK, called directly.** (B) Gemini's OpenAI-compatible endpoint with the `openai` SDK. (C) An abstraction layer such as LiteLLM or PydanticAI.
**Decision.** A, wrapped in our own thin `llm/client.py` (generate, generate_structured, run_tools, embed). That way we learn the real API, and swapping providers later only touches one file.
**Models** (from Google's models page, 2026-10-22):

- `gemini-3.8-flash`: **default** for extraction, drafting, and the agent. Stable, newest Flash, on the free tier.
- `gemini-3.5-flash-lite`: candidate for the high-volume pre-filter ("does this text contain a commitment?"). Decide with eval numbers in Phase 4.
- Pro-class (`gemini-4-argon`) is **paid-only**, so we won't use it.
- **Avoid** `-preview` **IDs.** Previews get shut down (`gemini-3-pro-preview` already has been), which would break the demo for reviewers.
**API details to confirm in Phase 1.** Google's current docs lead with the **Interactions API** (`client.interactions.create`, with `response_format` for JSON, `tools` for function calling, and `generation_config={"thinking_level": ...}`). It has a *stateful* mode (`previous_interaction_id`) where Google keeps the conversation on its side. **We use stateless calls:** we resend history ourselves and pass thought blocks back exactly as we got them. That keeps state on the Mac (ADR-014). Read the interactions and text-generation docs before writing the client.
**Tradeoffs.** Free-tier rate limits are low (check the AI Studio rate-limit page), so we need retries with backoff, response caching for evals, and the cheap pre-filter. The free tier isn't private (ADR-014). The Gemini SDK surface changes fast, so pin the version in `uv.lock`.
**Interview angle.** "I picked the provider on cost and fit, wrapped it so it's swappable, and chose stateless calls so conversation state never lives on someone else's server."

## ADR-020: Gemini embeddings (`gemini-embedding-2`, 768 dimensions), vectors stored locally

**Accepted** · 2026-10-24 · Phase 3

**Context.** We follow Minimi: Gemini computes the embedding, and the vector index lives on the Mac.
**Decision.** Use `gemini-embedding-2` with `output_dimensionality=768`, stored in sqlite-vec (ADR-007). Each vector row records `embed_model` and `embed_dims`, so we can re-embed if the model changes.
**Gotchas** (from Google's embeddings page, 2026-10-09):

- `task_type` is **not supported** on this model. Put the task in the text instead: queries as `task: search result | query: {text}`, documents as `title: {title or none} | text: {text}`.
- Truncated dimensions (768) are **auto-normalized**, so no manual normalization is needed. The older `gemini-embedding-001` does need it.
- Passing a list of strings returns **one combined embedding, not one per string**. Embed one text per call, or check the batch options, or retrieval will quietly break.
- Free tier: same data-use caveat as ADR-014. Cache embeddings by content hash, so the same text is never sent twice.
**Why 768 and not 3072?** It's 4× smaller to store, faster to search, and Google lists 768 among its recommended sizes. We can measure 1536 against 768 in the retrieval eval if there's time.
**Tradeoffs vs local embeddings (the old ADR-008).** Better quality and nothing to download, but memory text leaves the device, it needs the network, rate limits apply, and switching models means re-embedding everything.
**Interview angle.** "The vector index is local but the embedding is computed remotely. I can explain what that means for privacy: embeddings can be partly inverted back to text, so I treat them as sensitive as the text itself."

## ADR-021: Call Gemini through `models.generate_content` (stateless), not the Interactions API

**Accepted** · 2026-10-24 · Phase 1

**Context.** The Gemini docs now lead with the Interactions API (`client.interactions.create`). We read the installed SDK source (`google-genai` 2.33.0) to compare it with the classic call.
**Options.** (A) **`client.models.generate_content`.** Stateless by design: every request carries everything. Not deprecated. Supports `response_json_schema`, `thinking_config.thinking_level`, `automatic_function_calling.disable`, and `store`. (B) The Interactions API. Newer, built around server-side state (`previous_interaction_id`, `store`, `background`, webhooks), where state stays on unless you turn it off.
**Decision.** A. It's stateless without extra flags, which fits ADR-014. It's also the most widely documented surface. We also set **`store=False`** on every request, which asks Google not to log it. Retries use the SDK's built-in `HttpRetryOptions` (exponential backoff with jitter on 408/429/5xx, 5 attempts) instead of our own code.
**Tradeoffs.** New Google features may arrive in Interactions first. (`store=False` was confirmed working on the free tier in the first live run, 2026-10-25.)
**Revisit when.** `generate_content` is deprecated, or we need something only Interactions offers.
**Interview angle.** "I read the SDK source instead of trusting a blog post, and picked the API whose default is to keep no state."

## ADR-022: Plain `sqlite3` with hand-written SQL and `user_version` migrations, no ORM

**Accepted** · 2026-10-24 · Phase 1

**Options.** (A) SQLAlchemy or SQLModel. (B) **The standard library `sqlite3` with a `schema.sql` file.**
**Decision.** B. The schema lives in [schema.sql](brain/src/brain/db/schema.sql), and `PRAGMA user_version` tracks the version, so each migration runs once. Connections turn on WAL mode and foreign keys. The DB file is `chmod 0600` and its folder `0700`. Store functions don't commit. Callers group one unit of work in `with conn:`, so it lands all at once or not at all.
**Tradeoffs.** No ORM conveniences. But FTS5 and sqlite-vec (Phase 3) are SQLite-specific anyway, and ORMs get in the way of virtual tables. You also see every query.
**Interview angle.** "For a single-user local store, the stdlib driver plus explicit SQL is the simplest thing that works, and it keeps FTS5 and vector search first-class."

## ADR-023: CLI with Typer + Rich

**Accepted** · 2026-10-24 · Phase 1

**Options.** (A) `argparse` (stdlib). (B) **Typer** (type-hinted commands) with **Rich** (tables and panels).
**Decision.** B. The Phase 1 demo is the terminal, so readable tables and panels matter. Typer already depends on Rich, so it costs nothing extra.
**Tradeoffs.** Two small dependencies. The CLI is temporary. The Swift UI replaces it in Phase 6.

## ADR-024: Real first. Demo mode, fake mailbox, Docker, and recorded responses move to Phase 7

**Accepted** · 2026-10-24 · amends ADR-013, ADR-018

**Context.** Your call: the demo has to show real work (real Gemini, real Gmail, real capture). Reviewer conveniences come after the product works.
**Decision.** Phases 1–6 build only real paths. Moved to Phase 7: `DEMO_MODE`, `FakeMailbox`, the Dockerfile and compose file, and record/replay tests. Synthetic **fixtures stay**, because they're test *input data* for the pipeline (and needed for the free tier, ADR-014), not a fake mode. The live test (`pytest -m live`) checks the real API.
**Tradeoffs.** Until Phase 7, a reviewer would need the native toolchain. That's fine, since nobody reviews before Phase 7.

## ADR-025: Loop detection v0 is one call per observation, confidence ≥ 0.6, a grounding check, and exact-quote dedupe

**Accepted** · 2026-10-24 · Phase 1 (replaced by the two-stage engine in Phase 4)

**Decision.** For each new observation, one structured-output call returns `Detection{loops: [LoopCandidate]}`. Then:
1. **Confidence threshold.** Drop candidates below 0.6. False loops cost the user more than missed ones.
2. **Grounding check.** `evidence_quote` must appear in the source text, compared after normalizing whitespace and case. Otherwise the loop may be invented, so we drop it.
3. **Exact-quote dedupe.** If an open loop already has that quote, add the new observation as `progress` evidence instead of creating a duplicate.
4. **Date grounding.** The prompt includes the capture time with its weekday, so "by Wednesday" becomes an absolute `due_date`.
5. **Untrusted data.** Screen text goes inside `<screen_text>` tags, and the system prompt says it's data, never instructions.
**Tradeoffs.** One call per screen is expensive at real capture rates. Phase 4 adds a cheap pre-filter. Exact-quote dedupe misses paraphrases, and Phase 4 adds semantic matching. The 0.6 threshold is a guess until the loop eval tunes it.
**Interview angle.** "LLM output is a claim, so I verify it against the source before it becomes state."

## ADR-026: Actions are risk-classed tools behind connectors, with approval keyed on risk

Proposed · 2026-10-25 · Phase 5 · refines ADR-011, 012, 013

**Context.** Gmail is the only integration for the demo, but the pitch to Minimi is "this generalizes to every app you capture." `agent/draft.py` is a single-purpose Phase 1 step that Phase 5 replaces.
**Options.** (A) Gmail-specific agent code. (B) **A small `Connector` interface.** Each tool declares its schema plus a risk class (`read` / `draft` / `execute`). One generic approval gate: `execute` always needs a human click. (C) Adopt MCP for connectors now.
**Decision.** B in Phase 5, with Gmail as the only connector. Tools are shaped so that wrapping them as an MCP server in Phase 8 is mechanical.
**Tradeoffs.** A little more structure than a Gmail-only demo strictly needs. In return, the architecture slide can honestly say "adding WhatsApp is a new connector, not new safety code."
**Interview angle.** "Safety policy keys on what an action does (read, draft, execute), not on which app it touches, so the system scales to N integrations without N safety reviews."

## ADR-027: Live captures stay local on the free tier; detection needs paid or an explicit opt-in

**Accepted** · 2026-10-25 · Phase 2 · enforces ADR-014

**Context.** Phase 2 puts *your real screen* into the database. On the Gemini free tier, Google may use what we send and have humans review it.
**Decision.** Every observation records a `source` (`file` or `capture`, migration 002). Detection only picks up `capture` rows when `GEMINI_TIER=paid` or `ALLOW_FREE_TIER_LIVE=true`. Otherwise they're stored locally and counted as **held back**. Both `brain serve` and the menu show which mode you're in. Enforcement sits in one place (`pipeline.pending`), so the CLI and the worker can't disagree.
**Tradeoffs.** On the free tier, live capture doesn't produce loops until you opt in. That's intended. For the demo, opt in while only the test Gmail account and synthetic data are on screen.
**Interview angle.** "Data-governance rules are code paths with tests, not a line in the README."

## ADR-028: Swift Package + Makefile bundling instead of an `.xcodeproj`

**Accepted** · 2026-10-25 · Phase 2

**Options.** (A) An Xcode project: GUI-friendly, but `project.pbxproj` is hard to review in a diff and to generate from the CLI. (B) XcodeGen or Tuist: an extra tool to install. (C) **A Swift Package** (`app/Package.swift`) built with `swift build`, plus a `make app` step that wraps the binary in `ContextAgent.app` (Info.plist with `LSUIElement`) and signs it.
**Decision.** C. Plain text, reviewable, reproducible from the terminal (reviewers run `make app`), and Xcode still opens `Package.swift` for editing and debugging.
**Tradeoffs.** No asset catalogs or entitlements editor. We don't need them yet. Signing is done by hand with `codesign`.
**Gotcha.** TCC (the permission system) remembers the Accessibility grant against the app's **code signature**. With an Apple Development identity, it survives rebuilds. With ad-hoc signing (`-`), each build looks like a new app, so you'd have to re-grant (`make reset-permission`).

## ADR-029: Local API auth with a 0600 token file, a Host-header allowlist, and a 127.0.0.1 bind

**Accepted** · 2026-10-25 · Phase 2

**Context.** "It only listens on localhost" isn't security. Any web page you visit can make your browser send requests to `127.0.0.1:8765`, and with **DNS rebinding** it can even read the responses.
**Decision.** Three layers: (1) bind to 127.0.0.1 only, so nothing on your Wi-Fi can connect. (2) Every request needs `X-Brain-Token`, a random secret the brain writes to `~/Library/Application Support/ContextAgent/brain.token` with `0600` permissions. The Swift app reads it, and a web page can't. The comparison is constant-time (`hmac.compare_digest`). (3) A `TrustedHostMiddleware` allowlist (`127.0.0.1`, `localhost`) rejects rebinding requests, which arrive with a foreign `Host` header.
**Tradeoffs.** Any process running as *your* user could read the token. That's the normal desktop trust boundary, and the same is true of your SSH keys.
**Interview angle.** "Localhost services get attacked through the browser. I defend against it with a capability token and Host validation, and tests cover both."

## ADR-030: Capture triggers and dedupe: app switch + 5s poll, two-read debounce, masked line novelty

**Accepted** · 2026-10-25 · Phase 2

**Decision.**
- **Triggers:** read the frontmost window 1s after every app switch, and every 5s while you stay.
- **Debounce (app):** send only when the text, with digits masked, is identical on **two reads in a row**. That skips half-typed sentences and pages still loading.
- **Unchanged (app):** don't resend what was already sent for that window.
- **Near-duplicate (brain):** within 30 minutes of the last snapshot of the same window, store only if there's at least one **new line**, with digits masked.
- **Rate cap (brain):** detection starts at most once every 6s (about 10 calls a minute).
**How we got there:** we tried and rejected (1) Jaccard similarity ≥ 0.9, because one badge change on a short screen fell below the threshold, while a new message in a long Slack channel scored 0.944 and was *dropped*, and (2) a count of new word-triples, because "yep, will do" adds as many as a clock tick. Line novelty fits AX output, which is one UI element per line. Both failures are regression tests.
**Tradeoffs.** An edit that only changes a number (a due date of 28 → 30) is treated as unchanged. Polling isn't instant. AXObserver notifications could replace it later.

## ADR-031: How we read the AX tree: web area first, AXManualAccessibility, skip secure fields, batched reads, caps

**Accepted** · 2026-10-25 · Phase 2

**Decision.**
- Read the app's `AXFocusedWindow` (falling back to `AXMainWindow`). If the window contains an `AXWebArea`, read only that, which is the page and not the tabs, toolbar or bookmarks bar. Take the URL from the web area's `AXURL`, **with the query string removed** (it often carries tokens), keeping the fragment (Gmail thread IDs).
- Set `AXManualAccessibility = true` on every app. Chromium and Electron (Chrome, Slack, VS Code) only build their accessibility tree when an assistive app asks, and other apps ignore the attribute.
- `AXSecureTextField`: skip the subtree and **never request its value**. Password-manager and system apps are excluded *before* any read happens.
- Text comes from `AXValue` for text roles and from `AXTitle`/`AXDescription` for headings, links and buttons. Menu bars, scroll bars and images are skipped.
- Fetch role, subrole and children in **one** IPC call (`AXUIElementCopyMultipleAttributeValues`). Caps: 5,000 nodes, depth 60, 20,000 chars. Messaging timeout 0.5s, so a hung app can't freeze capture. Reads run off the main thread.
- **Added after testing on real apps (2026-10-25):**
  - Skip the ARIA landmark subroles Banner, Navigation, Search, Complementary and ContentInfo, and keep Main and Region. On a Gmail thread this cut 28% of the characters.
  - Once a text field returns its `AXValue`, don't read its children. Rich-text editors repeat the same words as child spans.
  - Strip invisible direction marks (U+200E and similar). WhatsApp puts them on every label.
  - Cut a single huge value (a code editor's whole file) to the remaining budget.
**Tradeoffs.** Canvas-rendered apps (Google Sheets cells, Figma) expose little or no text, and we accept the gap (ADR-005). Off-screen content in a long page may be included up to the cap. Gmail's message toolbar isn't exposed as `AXToolbar`, so about 10 lines of button labels remain.

## ADR-032: Event-driven capture with AXObserver, a coalescer, flush on leave, and a 30s backup poll

**Accepted** · 2026-10-25 · Phase 3 · supersedes the 5s poll in ADR-030

**Context.** A 5s poll plus a two-read debounce missed anything on screen for less than about 10s, such as a 7-second glance at an email (challenge #13).
**Decision.** Subscribe to the frontmost app's accessibility notifications (value, focus, window, title, selection, row count, live region, layout changes). A coalescer turns each burst into one read **1.5s after the last event, and never later than 5s after the first** (debounce with max-wait). Reads after a quiet period (`settled`) send right away, because the quiet period proves stability. On app deactivation (`leaving`), read the app one last time. A `poll` every 30s keeps the two-read rule for apps that send few notifications. Each capture carries its trigger (migration 003).
**Measured.** TextEdit sends `AXFocusedWindowChanged`, `AXFocusedUIElementChanged` and `AXValueChanged`. A 2s glance was captured (`settled`), and leaving didn't resend unchanged text.
**Gotchas, both fixed.**
1. macOS delivers the old app's *deactivated* **after** the new app's *activated*, so cancelling the scheduled read on deactivate killed the new app's first read.
2. A launching app refuses notification registration (`observing=0`), so we retry registration on each read, and retry a read that finds no window.
**Tradeoff.** Notification quality varies per app, so the backup poll stays.

## ADR-033: Episodes are one visit to one window, with lines merged, processed once when closed

**Accepted** · 2026-10-25 · Phase 3

**Decision.** An observation joins the open episode of the same `(bundle_id, window_title, source)` if it arrives within 5 minutes of the last one. Otherwise it starts a new episode. Episode text is **every distinct line seen during the visit, in first-seen order**, with digits masked for comparison. An episode closes after 5 minutes without a snapshot, and only closed episodes are processed. Loop detection moved from per-observation to per-episode, with the same prompt and grounding check, and evidence points to the snapshot that contains the quote.
**Why.** 30 near-identical snapshots of one visit cost the same as one: one text, one pair of LLM calls.
**Tradeoff.** Extraction lags the visit by 5 minutes. A window whose title never changes (one Slack channel all day) becomes one episode per visit, which is fine.

## ADR-034: One memory-extraction call per episode, structured, grounded, with provenance

**Accepted** · 2026-10-25 · Phase 3

**Decision.** `memory/extract.py` makes one structured-output call per closed episode and returns at most 8 `MemoryItem`s (`fact | decision | number | event | person | plan`). Each has a **standalone sentence** (names, dates and exact figures resolved, never "this"), a verbatim `quote` (grounding-checked like loops), and `entities`. Memories link to their episode and source observation, and go into FTS5 through triggers. A local gate skips episodes under 80 chars without an LLM call.
**Tradeoff.** Two calls per episode (memories + loops). Merging them would halve the calls (see ADR-037 and the quota question).

## ADR-035: Retention erases raw snapshot text after 7 days once processed

**Accepted** · 2026-10-25 · Phase 3

**Decision.** `brain purge` (and later the worker) erases `observations.text` for snapshots older than 7 days whose episode has been processed. The row stays (with `purged_at`), so loop evidence keeps its link. Memories are kept. Unprocessed snapshots are never erased.
**Why.** Keeping less raw screen text means less that can leak. Distilled memories are what's actually useful.

## ADR-036: Visibility culling skips off-screen and Chromium-clamped elements

**Accepted** · 2026-10-25 · Phase 3

**Decision.** Read `AXPosition` and `AXSize` in the same batched call as role and children. Skip an element and its subtree if its frame doesn't intersect the window, **or** if it's thinner than 2pt on one side, which is how Chromium reports scrolled-away content: clamped to the scroll edge as a 1pt sliver (measured in Cursor's chat: `y=143, height=1`). Exactly 0×0 means "unknown", so we keep walking. For long native text areas, try `AXVisibleCharacterRange` → `AXStringForRange` (parameterized attribute). Cursor doesn't support it, but the culling covers that case.
**Measured.** Notes 3,885 → 1,183 chars. Cursor 20,000 (capped) → 16,835 (not capped), with 400 subtrees skipped.

## ADR-037: Handle 429s ourselves: per-minute means wait the server's delay, per-day means stop the batch

**Accepted** · 2026-10-25 · Phase 3

**Context.** The free tier allows **20 `gemini-3.8-flash` requests per day**. The SDK retried daily-quota 429s five times with growing backoff (about 40s wasted each), and each failure used up an episode's 3 attempts.
**Decision.** The SDK retries only 408 and 5xx. Our client reads Google's 429 body: `QuotaFailure.quotaId` containing `PerDay` (or a `RetryInfo` delay over 60s) raises `QuotaExhausted`. The CLI stops the batch, and the worker pauses 30 minutes. A per-minute limit waits the server's `retryDelay` plus jitter, up to 3 times. Quota failures don't count against an episode's attempts.
**Interview angle.** "Retry policy depends on *why* you're limited. Per-minute means wait, per-day means stop."

## ADR-038: Retrieval defaults to hybrid RRF with recency off; duplicates need the same kind and nested numbers

**Accepted** · 2026-10-25 · Phase 3 · settles ADR-009

**Evidence** (`evals/results/retrieval.md`: 45 memories, 31 answerable queries, Flash-Lite extraction, `gemini-embedding-2` @ 768):

| Mode | Recall@1 | Recall@5 | MRR@10 | p50 search |
|---|---|---|---|---|
| BM25 | 84% | 97% | 0.884 | 0.2 ms |
| Vector | 90% | 100% | 0.946 | 0.6 ms |
| **Hybrid (RRF k=60)** | **90%** | 97% | 0.941 | 0.6 ms |
| Hybrid + recency | 81% | 97% | 0.879 | 0.6 ms |

Query embedding (network) p50 605 ms. Search itself is under 1 ms locally.
**Decision.** Default to `hybrid`. It ties vector on Recall@1 and wins exact-token queries (`PR #519`: BM25 1, vector 2, hybrid 1), which a work-memory tool gets asked constantly (ticket IDs, PR numbers, amounts). BM25 also works offline. **Recency off by default**, since it cost 9 points of Recall@1 because most questions aren't about "latest". Keep `hybrid_recency` for explicit "current / latest" questions later.
**Known weakness.** RRF demotes a result that only one retriever finds ("cohort chart on slide 4": vector 3 → hybrid 6). Weighted RRF or a reranker could fix it, but tuning on 31 queries would overfit.
**Caveat.** The differences are 1–3 queries out of 31: directional, not significant. Grow the eval set before tuning.
**Duplicates.** Cosine distance ≤ 0.075 **and** the same `kind` **and** one memory's number set ⊆ the other's (challenge #17).

## ADR-039: Flash-Lite (`gemini-3.5-flash-lite`) for testing and evals

**Accepted** · 2026-10-25 · Phase 3 · your call; partly settles the per-stage model question in ADR-019

**Context.** The `gemini-3.8-flash` free tier allows 20 requests a day (challenge #16).
**Decision.** Set `LLM_MODEL=gemini-3.5-flash-lite` for test and eval runs. The default in `config.py` stays `gemini-3.8-flash` until Phase 4 compares the two on the loop eval.
**Observed.** On the fixture week, Flash-Lite found **6 of 6** loops (Flash had found 5) with 0 false positives, but got the blog-post loop's counterparty wrong ("Dev"). It extracted 48 memories, mostly standalone and specific. Some low-value ones got through (a pytest failure, a SaaS renewal). 30 calls in about 2 minutes, with no quota errors.

## ADR-040: Loop lifecycle as an explicit state machine with a transition log

**Accepted** · 2026-10-25 · Phase 4

**Decision.** States `open → acting → awaiting_approval → closed | dismissed` with an explicit `ALLOWED` table ([lifecycle.py](brain/src/brain/loops/lifecycle.py)). `closed` and `dismissed` can be reopened. Every change writes a `loop_transitions` row (from, to, actor `system | user | agent`, reason, evidence observation, confidence). `closed_reason` records who closed it (`user`, `inferred`, `agent`), so the inbox can show "closed automatically" differently. Impossible jumps raise `InvalidTransition` (409 from the API).
**Deviation from the plan.** No `candidate` state: confidence turned out to be uncalibrated (ADR-042), so a "maybe" bucket would hold arbitrary loops. User **dismissals** play that role instead, and are labelled data for the eval.
**Migration 006** rebuilds `loops` (SQLite can't alter a `CHECK`): create → copy → drop → rename. **Gotcha:** with foreign keys on, `DROP TABLE loops` cascade-deletes all evidence, and `PRAGMA foreign_keys=OFF` is ignored inside a transaction. So the runner switches FKs off *around* the migration transaction and runs `PRAGMA foreign_key_check` afterwards. There's a regression test.

## ADR-041: Loop analysis v2: one call for new loops and tracked-loop updates, self-reminders, and semantic dedupe with a judge

**Accepted** · 2026-10-25 · Phase 4 · replaces ADR-025's detector

**Decision.**
- One structured call per episode returns `new_loops` and `updates` (`done | progress | still_open` for tracked loops). The prompt lists **related tracked loops**: the counterparty is named on screen, or it's the same window as the loop's evidence. That's chosen locally with no embedding call. Seeing them lets the model close loops *and* avoid recreating them.
- New direction **`self`** for concrete reminders to yourself (Minimi treats these as loops). Meeting action items assigned to you count as `i_owe`. Each loop gets a **`note`** ("why it's still open") for the inbox.
- Cross-episode dedupe: exact quote → vector KNN over `loop_vectors` → an LLM **judge** ("same commitment?") only for pairs under the calibrated distance (ADR-043).
- A "done" below 0.8 confidence, or one the verifier rejects, is recorded as progress evidence, never a close.

## ADR-042: Model per stage (free tier): Flash-Lite everywhere, with 3.8 Flash as the measured upgrade for loop analysis

**Accepted** · 2026-10-25 · Phase 4 · settles ADR-019's per-stage question for now

**Evidence** (`evals/results/`):

| Set | Model | Precision | Recall | Due dates | Unsafe closes |
|---|---|---|---|---|---|
| loops (43, written with the prompt) | Flash-Lite | 100% | 100% | 14/14 | 0 |
| **holdout (16, harder, never tuned on)** | Flash-Lite | **91%** | 100% | 8/8 | 0 |
| **holdout** | 3.8 Flash | **100%** | 100% | 8/8 | 0 |

**Decision.** Flash-Lite for memory extraction, loop analysis, the judge and the verifier while on the free tier (quota). 3.8 Flash is better on precision (it avoided the FYI-forward false loop), so it's the upgrade for **loop analysis**, the stage you see, once there's a paid key.
**Confidence threshold stays 0.6, because it doesn't matter.** The sweep (0.5 → 0.9) is flat: the model reports ≥ 0.9 on nearly everything, including its mistakes. Self-reported LLM confidence is **uncalibrated**, so precision has to come from the rules, the verifier and your dismissals.

## ADR-043: Generator + verifier for closes, and a judge threshold calibrated at 0.14

**Accepted** · 2026-10-25 · Phase 4

**Context.** In an end-to-end run, the analysis call closed *"Countersign Contoso renewal"* because Jordan's *NDA* email said "Attached the signed NDA": same person, different deliverable. An unsafe close hides a real deadline.
**Decision.** Every proposed close goes to [verify.py](brain/src/brain/loops/verify.py), one narrow yes/no call: "does this text show *this exact deliverable* was delivered, or cancelled by the person owed?" Only verified closes happen. Measured: Contoso + NDA email → `false` ("a signed NDA, not the countersigned renewal"). Positive control, "Send Jordan the signed NDA" + the same email → `true`. No real close was vetoed in either eval set (5/5, 1/1).
**Judge threshold.** Paraphrases of the same loop: 0.022 / 0.041 / 0.105. Closest *different* loops: 0.164 / 0.182 / 0.198 (37 of 55 different pairs were under the original 0.30). So the threshold is 0.14, with at most 2 judge calls per new loop. Calls per fixture run dropped from 92 to 67.
**Interview angle.** "The riskiest action gets its own narrow verifier. Generation is broad, verification is specific."

## ADR-044: Gmail via google-api-python-client, scopes readonly + compose, OAuth token in the macOS Keychain

**Accepted** · 2026-10-25 · Phase 5 · refines ADR-013

**Decision.** `google-api-python-client` + `google-auth-oauthlib` (installed-app flow: a browser consent screen once, `brain gmail-login`). Scopes: `gmail.readonly` (read threads) + `gmail.compose` (drafts). The refresh token is stored with `keyring` in the **macOS Keychain** (service `ContextAgent`), never in a file. Access tokens refresh automatically. Replies set `threadId` **and** `In-Reply-To` / `References` to the last message's `Message-ID`, so they thread for the recipient too (tested against canned API responses).
**Key limitation.** `gmail.compose` also allows **sending**. Google has no "drafts only" scope. So the guarantee "the model can't send" can't come from OAuth, and comes from our architecture instead (ADR-045, ADR-046).
**Tradeoffs.** Three new dependencies. The Google Cloud app is in "testing" mode (only your test accounts can log in), which is fine for a prototype.

## ADR-045: The agent: hand-written loop, provider-neutral tool types, risk-classed tools with guardrails in code, and no send tool

**Accepted** · 2026-10-25 · Phase 5 · implements ADR-011, ADR-012, ADR-026

**Decision.**
- **Loop** ([agent/loop.py](brain/src/brain/agent/loop.py)): model turn → validate and run each tool call → send all results back in one user turn → repeat until `finish`. Budgets: 10 turns, 80k tokens, plus one nudge if the model stops without calling `finish`. A failed run reopens the loop and **deletes any draft**, so no stray drafts are left in Gmail.
- **Provider-neutral:** the agent sees our `ToolSpec / ToolCall / Step`. Only `llm/client.py` knows Gemini. Its `Conversation` appends each model turn **exactly as received** (thought signatures intact), and returns tool results as `Content(role="user", parts=[function_response…])`, the same as the SDK's own loop.
- **Tools** ([agent/tools.py](brain/src/brain/agent/tools.py)): `search_memory`, `mail_search`, `mail_get_thread` (read), `create_draft` (draft), `finish`. Arguments are validated with Pydantic before running. Results from email or memory are labelled `untrusted_*`.
- **Guardrails in code:** recipients must already be in the thread; no drafting into a thread the agent hasn't read; one draft per run; `finish(drafted)` requires a draft. There are no `execute` tools, and an `assert` enforces it.
- **Audit:** one `agent_run` action, with a child row per tool call (`ok | refused | error`).
- **Authority rule** (added after the eval caught an overstep, challenge #23): never accept, renew, agree to terms or pick times for the user, and use a `[[placeholder]]` instead.

## ADR-046: Approval protocol: approve the hash you saw, claim once, send, then verify in Sent before closing

**Accepted** · 2026-10-25 · Phase 5

**Decision** ([agent/approval.py](brain/src/brain/agent/approval.py)):
1. The UI sends back `draft_hash` (sha256 of recipients, subject and body) for the draft it **displayed**. If it doesn't match, the approval is refused. That prevents approving one thing and sending another (TOCTOU, time-of-check vs time-of-use).
2. **Claim once:** `UPDATE … SET status='sending' WHERE status='awaiting_approval'`. Only one request wins, so a double click or a retried request can't send twice.
3. An edited body (from the UI) updates the draft first, so what you edited is what goes out.
4. Send, then **verify**: read the message back and require the `SENT` label and the same thread. Only then does the loop close (`closed_reason = agent`), with the message id in the audit log. Otherwise the status is `sent_unverified` and the loop stays awaiting.
5. Reject deletes the draft and reopens the loop.
**Endpoints:** `POST /loops/{id}/close`, `GET /actions/{id}`, `POST /actions/{id}/approve`, `POST /actions/{id}/reject`. The CLI equivalents are `brain close / approve / reject`.

## ADR-047: FakeMailbox pulled forward from Phase 7 for tests and agent evals

**Accepted** · 2026-10-25 · amends ADR-024

**Context.** Agent tests and evals need a deterministic mailbox. Testing against a real inbox is slow, flaky and a privacy problem.
**Decision.** [mailbox/fake.py](brain/src/brain/mailbox/fake.py) implements the same `Mailbox` interface in memory. It's used by tests, by `evals/run_agent.py`, and later by the Phase 7 demo mode. The real paths stay real: `brain close` and the API use Gmail.

## ADR-048: Scoped mailbox: a fixed Gmail filter on every agent search, required on the free tier

**Accepted** · 2026-10-25 · Phase 5 · enforces ADR-014/027 for the agent

**Context.** The connected test account is your **main** inbox (about 8,800 real emails). The agent chooses its own searches, so a query like "Priya retention" could pull real emails into prompts sent to the free tier. OAuth can't narrow this: `gmail.readonly` reads everything.
**Decision.** [ScopedMailbox](brain/src/brain/mailbox/scoped.py) appends `MAIL_SCOPE` (e.g. `subject:"[CA-TEST]"`) to every search as `(<query>) <scope>`. Only threads a scoped search returned can be opened or drafted into, so a thread id the agent guessed or read in injected text is refused. On the free tier, `open_mailbox` **refuses** to give the agent an unscoped real mailbox. Set `MAIL_SCOPE`, or use a paid key.
**Verified live** (2026-10-25, real Gmail): the agent found only the `[CA-TEST]` seed thread. Tests cover search scoping, an out-of-scope thread refused, and an unscoped free-tier mailbox refused.
**Interview angle.** "When the OAuth scope is too broad, add least privilege one layer up, at the query level."

## ADR-049: Agent progress over Server-Sent Events (SSE)

**Accepted** · 2026-10-25 · Phase 6

**Context.** An agent run takes 5–10 s. A spinner with no feedback feels broken, and the steps themselves build trust ("Searching your mail → Reading the thread → Looking up your memories → Drafting").
**Options.** (A) Polling `GET /actions/{id}`: simple, but laggy and chatty. (B) **SSE**: one HTTP response that stays open and streams `data: {json}` lines, server → client. (C) WebSockets: two-way, but needs more machinery than we need (the client never talks mid-run).
**Decision.** B. `POST /loops/{id}/close/stream` runs the agent in a worker thread (with **its own SQLite connection**) that pushes `thinking / step / done / error` events into a queue, and the response drains it. Swift reads it with `URLSession.bytes(for:)` + `.lines` into an `AsyncThrowingStream`. The mailbox is resolved *before* the stream starts, so "Gmail not connected" is a clean 503, not a half-started run.
**Tradeoff.** If the connection drops mid-run, the run still finishes server-side and the inbox picks up the draft on its next refresh ("resume pending drafts").

## ADR-050: Inbox UI as a Minimi-style panel + dashboard + settings, with trust guards in the UI

**Accepted** · 2026-10-25 · Phase 6

**Decision.**
- **Panel** (menu bar, with the open-loop count next to the icon), **dashboard** window (Inbox + Recent memories), **Settings** window (capture, what leaves your Mac, delete all data).
- Loop cards show app icon · window · due badge, the title, who owes whom plus the *why*, the source quote, and **Close it for me** · Resolve · Not a loop. App filter chips. Closed loops say *how* they closed (you / inferred / agent), with a link to the sent email.
- **Trust guards:** all model and screen text is rendered with `Text(verbatim:)` (no Markdown or link injection). **Approve & Send stays disabled while any `[[placeholder]]` remains.** Approve sends the hash of the displayed draft. Refused tool calls are shown ("refused by a guardrail"). Drafts awaiting approval are restored after an app restart.
- Backend additions: `bundle_id`, `proof_url` and the last run on `/loops`; `GET /memories`; `POST /data/delete` (an exact confirmation phrase, then `VACUUM` so deleted text doesn't linger in the file); `agent_ready` / `agent_detail` on `/status` (checked locally, no network).
- A fresh Gmail connection per run: Google's `httplib2` client isn't thread-safe.

## ADR-051: Demo-ready flow: a live scope on the free tier, and ending the visit when you leave a window

**Accepted** · 2026-10-25 · Phase 6 · refines ADR-027 and ADR-033

**Context.** Your test feedback: the flow has to work like the demo, with no commands. Two of our choices blocked that. (1) On the free tier, live captures were held back unless you opted in, and the opt-in sent *everything* on screen. (2) A visit was processed only after 5 minutes of silence.
**Decision.**
1. **`LIVE_SCOPE='[CA-TEST]'`:** on the free tier, live episodes whose window title or text contains the marker are processed automatically. Every other capture stays on the Mac (held back). It's the capture-side twin of `MAIL_SCOPE`. Paid tier: everything is processed as before.
2. **End of visit:** when you switch away from an app, the app calls `POST /visits/end`, and the brain closes that window's episode immediately, so the worker picks it up within ~2 s. The 5-minute gap stays as the fallback.
3. The panel and dashboard refresh every 3 s while open, and show *"Checking what you just looked at…"* while episodes are pending.
**Demo setup:** `.env` has `LLM_MODEL=gemini-3.5-flash-lite`, `MAIL_SCOPE='subject:"[CA-TEST]"'`, `LIVE_SCOPE='[CA-TEST]'`. Then just `make brain` + the app.
**Tradeoff.** The scope is a subject or title convention, which suits a demo and is safe on the free tier. With a paid key, drop both scopes for real use.

## ADR-052: Your call: remove the free-tier gating and both scopes, so every capture is processed

**Accepted** · 2026-10-25 · supersedes ADR-027, ADR-048 and the live-scope part of ADR-051

**Context.** The `[CA-TEST]` markers read as hard-coded and get in the way of a natural demo. You'll manage Gemini usage yourself, mainly for tomorrow's demo shoot.
**Decision.** Removed `GEMINI_TIER`, `ALLOW_FREE_TIER_LIVE`, `LIVE_SCOPE`, `MAIL_SCOPE` and the `ScopedMailbox`. Every closed episode is processed. The agent sees your connected Gmail. Kept: the end-of-visit trigger (ADR-051), the app denylist, password-field skipping, redaction, and everything about sending (no send tool, recipients pinned to the thread, approval of the exact draft, verify in Sent).
**Tradeoff, stated plainly.** On Gemini's free tier, text sent may be used by Google and reviewed by people. With the app running, that's every window you visit, and the agent's reads of your real inbox. The controls left are **pause capture** (panel toggle), **"Never capture <app>"**, and the built-in denylist. A paid key changes the data terms.
**Kept as history** in ADR-027 / 048, including the reasoning, which is still a good interview story about data governance.

## ADR-053: No thread means a new email, with recipients only from the loop's known contact or from you

**Accepted** · 2026-10-25 · your design · amends ADR-012 / ADR-045

**Context.** Commitments to email someone are made everywhere: WhatsApp ("kal mail kar dunga"), Notes, meetings. Reply-only meant "an email can't close this" for all of them.
**Decision.** The agent's procedure is now: find the thread → reply in it. **No thread → `create_new_email`.** If the loop has the counterparty's address (seen on screen), it's pre-filled. If not, To is empty and the inbox asks you for it. `cannot_close` is now only for things an email can't do (reminders to yourself, tasks like reviewing code).
**The security change, and why it's still safe.** "Recipients must be in the thread" was the prompt-injection guard, and a new email has no thread. Replacement:
1. The **model** may address a new email **only** to the loop's known counterparty address, or leave it blank. Anything else is refused in code, so injected text can't choose a recipient.
2. **You** can type any recipient, in the UI (validated), because you're the trusted party.
3. A **reply's** recipients still can't be changed at approval.
4. Nothing sends without Approve, and Approve stays disabled with no valid recipient or with `[[placeholders]]` left.
5. **Right-person rule** (found by the eval): if the loop knows the counterparty's address, a thread only counts if that address is in it. A same-named person at another address is a different conversation, so the agent writes a new email instead.
**Verify:** a new email counts as delivered when Gmail shows it as SENT (it starts its own thread). The proof link uses the sent message's thread.

## ADR-054: Prompt rules that kept flaking became code: an authority verifier and a right-person check

**Accepted** · 2026-10-25 · Phase 6 · extends ADR-043's generator + verifier pattern

**Context.** After the new-email procedure made the prompt longer, the agent eval went 11/12 → 10/12 → 12/12. Flash-Lite followed two prompt rules less reliably: it **renewed the lease for you** in 2 of 3 runs, and **replied to a same-named stranger** in 1 of 3.
**Decision.**
1. **Right-person check (deterministic):** `create_draft` refuses a thread that doesn't include the loop's known counterparty address, and tells the model to use `create_new_email`.
2. **Authority verifier (generator + verifier):** before any draft is saved, a narrow call asks one question: *does this draft decide, accept, decline, renew, agree to terms, pick times or commit the user to something new?* If yes, the save is refused, and the model must use a `[[placeholder]]` and list it in missing_info. Then the UI's placeholder guard blocks Approve.
**Cost.** One small extra call per draft (about 1 s), on the behaviour that matters most to the pitch.
**Interview angle.** "When a rule flaked in the eval, I moved it from the prompt into code. Deterministic where possible, a narrow verifier where it needs judgement."
**Measured after the change** (real model, 3 runs): lease and wrong-person **fixed** (passed every run they ran in). New: the verifier **over-blocked** "confirm the PyCon talk slot" (2/2 runs lost the time). Confirming was the owed task, not a new decision. The verifier wording was tightened to block only decisions *beyond what's owed*. **Re-measured 2026-10-26: 12/12**, with PyCon confirming 2:30 and the lease's first draft blocked by the verifier before the agent rewrote it with a placeholder. One run so far (see `docs/eval-report.md`).

## ADR-055: No Docker. The reviewer runs the brain with `uv` and the app with `make`

**Accepted** · 2026-10-26 · Phase 7 · your call · supersedes the Docker part of ADR-018 / ADR-024

**Context.** ADR-018 planned a Docker image for the brain so a reviewer gets identical dependencies. But the app can't run in Docker at all (Docker on macOS is a Linux VM with no Accessibility API), so the reviewer needs a Mac with the Swift toolchain anyway.
**Options.** (A) Docker brain + native app (ADR-018). (B) **Native both: `uv` for the brain, `make` for the app.**
**Decision.** B. `uv sync` installs the exact locked versions from `uv.lock`, which was the reproducibility Docker was meant to buy. The quickstart is now `.env` → `make brain` → `make run-app`, written in `readme.md`.
**Tradeoffs.** Lost: a fully isolated brain, and a headless path for non-Mac reviewers (nobody can run the product without a Mac anyway). Gained: one fewer tool to install (Docker Desktop is about 2 GB), no bind-mount and port-mapping config to get wrong, faster first start, and nothing to keep in sync between the dev path and the reviewer path.
**Revisit when.** Shipping for real: then the brain is bundled inside the signed `.app` and started by it.

## ADR-056: Reading a window closes every other open visit, and the newest visit is processed first

**Accepted** · 2026-10-29 · Phase 7 · extends ADR-051

**Context.** Live in Notes, loops showed up minutes late or not at all. There were two causes:
1. Notes puts the note count in the window title ("All iCloud – 53 notes" → "New Folder – 1 note"), so opening another note is a *new window* to us. The old one never gets a "leaving" read, so it stayed open until the 5-minute gap. The same thing happens when an app quits: the leaving read finds no window, so no end-of-visit is sent.
2. The worker processed the oldest closed episode first, so the visit you just left could queue behind a large earlier one.
**Decision.** The app only ever reads the frontmost window, so a `settled` or `poll` read of window B means every other window's visit is over. `episodes.assign` closes all other open capture episodes. A `leaving` read never closes others, because it can arrive after the next window was read. The worker takes the most recently closed episode first.
**Tradeoffs.** Going back to a window within 5 minutes now starts a new episode, so that window is processed again. The extra cost is a few calls, and dedupe catches repeated memories and loops. Old episodes wait while you keep moving, but they still drain.

