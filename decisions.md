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
| 001 | The wedge is an action agent that closes loops, with a human approving | Proposed |
| 002 | Prototype, not product | Proposed |
| 003 | Walking skeleton first | Proposed |
| 004 | Swift app plus a Python brain on localhost | **Accepted** |
| 005 | Accessibility API only, never screenshots | **Accepted** |
| 006 | ~~Claude as the LLM~~ | Superseded by 019 |
| 007 | SQLite + FTS5 + sqlite-vec in one local file | Proposed |
| 008 | ~~Local fastembed embeddings~~ | Superseded by 020 |
| 009 | Hybrid retrieval with RRF, chosen by eval | Proposed |
| 010 | Structured outputs with Pydantic everywhere | Proposed |
| 011 | Hand-written agent loop, no framework | Proposed |
| 012 | Drafts by default, sending needs a human click | Proposed |
| 013 | Gmail API directly | Proposed |
| 014 | Privacy model: local storage, minimal egress, honest disclosure | Proposed (updated) |
| 015 | Small hand-labeled evals from day one | Proposed |
| 016 | MCP in v2 | Proposed |
| 017 | Python tooling: uv, FastAPI, Pydantic, pytest | Proposed |
| 018 | Runs on a reviewer's Mac: Docker brain, native app, demo mode | **Accepted** (details proposed) |
| 019 | Gemini as the LLM through the official `google-genai` SDK | **Accepted** |
| 020 | Gemini embeddings (`gemini-embedding-2`, 768 dimensions), stored locally | **Accepted** |

---

## ADR-001: Our wedge is an action agent that closes loops, with a human approving
Proposed · 2026-10-24 · Phase 0

**Context.** Minimi's public site (read 2026-10-24) describes capture through Apple's accessibility infrastructure, local memory, an MCP connector, and an "Open loops Inbox" that *finds* loops and "resolves closed loops" when it sees they're done. It doesn't describe the app taking outward actions like sending an email for you. A prototype that copies Minimi proves nothing. One that adds the obvious next step shows product sense.
**Options.** (A) Clone Minimi more cheaply. (B) Better memory accuracy. (C) **Act on loops**: draft, approve, send, verify, close.
**Decision.** C, with Gmail replies as the first and only action.
**Tradeoffs.** Actions add risk (wrong recipient, prompt injection) and need OAuth. We reduce that with drafts-first plus human approval (ADR-012). We spend less time on capture breadth and memory quality.
**Revisit when.** Minimi ships actions themselves. Then pitch a different action, such as calendar or Slack.
**Interview angle.** "Finding a loop is half the value. Closing it is where time is saved, but only if the user stays in control of anything that leaves their machine."

## ADR-002: Build a prototype, not a product
Proposed · 2026-10-24 · Phase 0

**Context.** The goal is an interview, plus learning. Time spent on production concerns doesn't show up in a 3-minute demo.
**Decision.** Single user, Apple Silicon, English, Gmail only, local only, unsigned dev build. No accounts, billing, sync, or App Store sandbox. It still has to run cleanly on a reviewer's Mac (ADR-018).
**Tradeoffs.** It isn't something you'd hand to the general public. The demo is a video, plus a repo that runs.
**Interview angle.** "I scoped hard to the riskiest, most differentiating path and wrote down what I cut."

## ADR-003: Walking skeleton first
Proposed · 2026-10-24 · Phase 1

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
Proposed · 2026-10-24 · Phase 1/3

**Options.** (A) Postgres + pgvector, which means running a server. (B) Chroma or LanceDB, a separate store from the relational data. (C) **SQLite with extensions.**
**Decision.** C. One local file holds relational data, keyword search, and vectors (768 dimensions, ADR-020). It lives at `~/Library/Application Support/ContextAgent/brain.db`, and in Docker that folder is bind-mounted (ADR-018). Deleting everything is one folder. Nothing extra has to run.
**Tradeoffs.** sqlite-vec does brute-force or simple index search, which is fine up to roughly 100k vectors (our demo has hundreds). There's a single writer, which is fine because the brain is the only writer. Check that sqlite-vec has a linux/arm64 wheel for the Docker image.
**Interview angle.** "Local-first means the database ships inside the app. SQLite is the standard choice for that."

## ADR-008: Local embeddings with fastembed
**Superseded by ADR-020** · 2026-10-24

The original proposal was on-device embeddings (bge-small, 384 dimensions) so memory text would never leave the Mac. We replaced it to follow Minimi's approach (Gemini embeddings) for better quality and no model download. fastembed stays as a possible **offline/strict-privacy mode** in Phase 8, behind the same `embed()` interface.

## ADR-009: Hybrid retrieval (BM25 + vectors) with Reciprocal Rank Fusion, chosen by eval
Proposed · 2026-10-24 · Phase 3

**Context.** Queries mix exact tokens ("Q3", "Priya") with fuzzy meaning ("the retention stuff").
**Decision.** Implement BM25, vector, and hybrid (RRF, k=60) with recency weighting. Ship whichever wins Recall@5 and MRR on our eval set.
**Tradeoffs.** More moving parts than a single method. RRF ignores raw score sizes, which is a feature, since BM25 and cosine scores aren't comparable. BM25 runs fully offline, so if the Gemini API is down or rate-limited, keyword search still works.
**Interview angle.** "Keyword search catches names and numbers, vectors catch paraphrases, and RRF combines them without having to calibrate scores."

## ADR-010: Every LLM extraction uses structured outputs with a Pydantic model
Proposed · 2026-10-24 · Phase 1

**Decision.** Define the output as a Pydantic model and pass its JSON Schema to Gemini as the response format (`mime_type: application/json` plus the schema). Then validate with `Model.model_validate_json(...)`. Never regex-parse free text. Use this for loop candidates, memories, and judge verdicts.
**Tradeoffs.** The schema has to be designed carefully, since too many required fields leads to invented values. So include `confidence` and a nullable `due_at`. We validate even though the API constrains the output, because schema support has limits and the check costs nothing.
**Interview angle.** "The output schema is the contract between the LLM and the rest of the system, and I still validate at the boundary."

## ADR-011: A hand-written agent loop, with no agent framework or SDK auto-calling
Proposed · 2026-10-24 · Phase 5

**Options.** (A) LangChain, LangGraph, CrewAI, or Google ADK. (B) The SDK's automatic function calling, where it runs your Python functions for you. (C) **A manual loop**: send tools, read the `function_call` steps, run them ourselves, send back the `function_result`s, and repeat.
**Decision.** C. We own the loop, so we can enforce the step limit, the allowlist, the approval gate, and the audit log at each call. Gemini thinking models return thought blocks or signatures that must be passed back unchanged in stateless mode. Learning that is part of the exercise.
**Tradeoffs.** More code to own. In return, you'll understand every step, which is what interviewers probe, and our guardrails sit *in* the loop instead of wrapped around a black box.
**Interview angle.** "I can explain the agent loop without a framework, and our safety checks live inside it."

## ADR-012: Drafts by default, sending needs a human click, and all tool content is untrusted
Proposed · 2026-10-24 · Phase 5

**Context.** The agent reads untrusted text (screen content and emails), has access to private data (memory), and can communicate outward (email). That combination is the classic setup for prompt injection to exfiltrate data.
**Decision.** The model can only create drafts. `send` isn't a model tool, so only the approval endpoint calls it. Recipients must already be in the thread. Untrusted content is delimited and labeled as data. The agent has a step and token budget, and every action is written to the audit log. A prompt-injection regression test is required.
**Tradeoffs.** It's less "magical" than full autonomy. That's intended: it makes for a better trust story than an agent that sends on its own.
**Interview angle.** "Break the injection chain by removing autonomous outward communication, not by hoping the prompt holds."

## ADR-013: Call the Gmail API directly, with a fake mailbox for demo mode
Proposed · 2026-10-24 · Phase 5

**Options.** (A) **Gmail API with Google's Python client.** (B) An integration platform such as Composio. (C) A Gmail MCP server.
**Decision.** A, behind a `Mailbox` interface with two implementations: `GmailMailbox` (real OAuth) and `FakeMailbox` (a local JSON inbox seeded from fixtures, for demo mode and tests; ADR-018).
**Tradeoffs.** Hand-written auth and token refresh. It won't scale to many integrations. Mention B and C as the path to scaling.
**Interview angle.** "Do one integration deeply, put it behind an interface, and fake it for tests and demos."

## ADR-014: Privacy model with local storage, minimal egress, and honest disclosure
Proposed (updated for Gemini) · 2026-10-24 · Phase 2

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
Proposed · 2026-10-24 · Phase 3–5

**Decision.** Three small eval sets: retrieval (about 30 queries), loops (about 40 snippets), and agent tasks (about 10). Each has a runnable script and saved results. Re-run them after every prompt or model change. To fit within free-tier rate limits, cache embeddings and LLM responses keyed by (model, prompt hash).
**Tradeoffs.** Small samples are noisy, so report counts as well as percentages. It's labelling work, but it's also the best interview material you'll have.
**Interview angle.** "Without evals, prompt changes are guesswork. I can show what each change did to the numbers."

## ADR-016: Push MCP to v2
Proposed · 2026-10-24 · Phase 8

**Context.** Minimi already ships a memory MCP, so it's not our differentiator. The readme already marks MCP as v2.
**Decision.** Build it after the demo works, as a thin layer over existing functions.
**Interview angle.** "MCP is an interface over the core. The core value is loops and actions."

## ADR-017: Python tooling is uv, FastAPI, Pydantic v2, and pytest
Proposed · 2026-10-24 · Phase 0

**Decision.** `uv` for environments and the lockfile (`uv.lock`), which the Docker image also builds from, so dev and Docker get identical dependencies. FastAPI because it's typed, builds on Pydantic, and makes SSE streaming easy. pytest for tests.
**Tradeoffs.** None worth noting. These are the defaults in modern Python AI work.

## ADR-018: Runs on a reviewer's Mac with a Docker brain, a native app, and demo mode
**Accepted** (implementation details proposed) · 2026-10-24 · Phase 1 onward

**Context.** You'll send the GitHub repo to companies. A reviewer should go from `git clone` to a working demo in minutes, without installing a Python toolchain, without creating Google OAuth credentials, and ideally without granting powerful permissions to an unknown app.
**Key constraint.** Docker on macOS runs a **Linux VM**. Code inside a container can't call macOS APIs, so it can't read the Accessibility tree or show a menu-bar UI. Docker can run the **brain** but not the **app**.
**Options.**
- (A) Docker for everything. Impossible for the app.
- (B) Native only (uv and Xcode). Reviewers need a matching toolchain.
- (C) **Docker for the brain, native for the app, plus a demo mode that needs neither real capture nor real Gmail.**
**Decision.** C.
- `docker compose up` builds the brain from the same `uv.lock` and maps the port **only to localhost** (`127.0.0.1:8765:8765`, so it isn't exposed on the network). Data goes to a bind-mounted folder on the Mac, not inside the container.
- The app runs from `make app` (`xcodebuild`), or from a prebuilt `.app` attached to a GitHub Release. It's ad-hoc signed, so the README explains right-click → Open.
- **`DEMO_MODE=1`** replays fixture "screen sessions" in place of live capture and uses `FakeMailbox` in place of Gmail. A reviewer needs **one thing: a free Gemini API key**. Since the data is synthetic, the free tier is fine (ADR-014).
- There's a headless path too: `docker compose run brain demo` prints the whole flow (loops detected, agent steps, draft) in the terminal. It works on any OS, even without the Mac app.
- For your own development, `uv run` natively is faster. Both paths share one lockfile.
- CI (GitHub Actions) builds the image and runs the tests against **recorded LLM responses**, so CI needs no API key and the README can show a green badge.
**Tradeoffs.** Docker adds a little complexity (Dockerfile, compose file, volume paths) and a slower first start. The reviewer still has to run the native app separately. Recorded responses can drift from live model behaviour, so re-record them when prompts change.
**Revisit when.** Shipping for real. Then you'd bundle the brain inside the signed `.app` and drop Docker.
**Interview angle.** "I designed it so you can run the demo in two commands with zero credentials beyond a free key, and I know exactly why the Mac half can't be containerized."

## ADR-019: Gemini as the LLM, through the official `google-genai` Python SDK
**Accepted** · 2026-10-24 · Phase 1 (model per stage settled in Phase 4)

**Context.** It has to be free to build and free for reviewers to run. Gemini's Flash models have a free tier, and Minimi also uses Gemini.
**Options.** (A) **The official `google-genai` SDK, called directly.** (B) Gemini's OpenAI-compatible endpoint with the `openai` SDK. (C) An abstraction layer such as LiteLLM or PydanticAI.
**Decision.** A, wrapped in our own thin `llm/client.py` (generate, generate_structured, run_tools, embed). That way we learn the real API, and swapping providers later only touches one file.
**Models** (from Google's models page, 2026-10-22):
- `gemini-3.8-flash`: **default** for extraction, drafting, and the agent. Stable, newest Flash, on the free tier.
- `gemini-3.5-flash-lite`: candidate for the high-volume pre-filter ("does this text contain a commitment?"). Decide with eval numbers in Phase 4.
- Pro-class (`gemini-4-argon`) is **paid-only**, so we won't use it.
- **Avoid `-preview` IDs.** Previews get shut down (`gemini-3-pro-preview` already has been), which would break the demo for reviewers.
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
