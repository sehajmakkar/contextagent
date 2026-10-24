# CLAUDE.md

Guidance for Claude (and any AI pair-programmer) working in this repo. Read this first, every session.

## What this project is

**macOS Context Agent**: a local-first Mac assistant that reads what's on screen through the Accessibility API, remembers it, finds your **open loops** (promises, follow-ups, unanswered asks), and then **closes them for you**. It drafts the email reply, you approve it, it sends, and the loop is marked done with evidence.

It's inspired by [Minimi](https://www.projectminimi.com/), which captures context, builds memory, and shows an "Open loops Inbox". **Our addition is the action agent.** Minimi finds and tracks loops. We add an agent that does the work to close them, with a human approving every outward action.

### Why it exists (this decides most tradeoffs)

1. **Get an interview, then an offer**, at Minimi, Clicky, and similar companies (see `readme.md`). The deliverable is a **polished demo prototype** plus a **GitHub repo that runs on a reviewer's Mac in minutes**. It is not a product.
2. **Learn the AI engineering concepts in depth.** The user must be able to explain every technology, decision, and tradeoff in an interview.

So: demo quality, the ability to reproduce it, and understanding come before completeness. When unsure, choose whatever makes a sharper 3-minute demo and a better interview story.

## Teaching protocol (mandatory)

The user is learning while building. Every task follows this loop:

1. **Before coding, give a brief.** In a few lines: what we're building, which concepts it touches (link to `learnings.md` entries), and which decisions it needs.
2. **Make decisions explicit.** For any real choice (library, model, schema, algorithm, architecture), give the options, your recommendation, and the tradeoffs. Record it as an ADR in `decisions.md`. Never pick a technology silently, and never add a dependency without at least a one-line ADR. When a decision changes, mark the old ADR superseded. Don't delete it.
3. **Explain the why while coding.** Comments stay normal and sparse. Explanations go in the chat reply, with links to `file:line`.
4. **After the task, update `learnings.md`.** Add or extend an entry for each new concept: what it is, how it works, where it lives in our code, gotchas we hit, and 1–2 interview questions with short answers.
5. **Let the user write the core pieces.** For key AI pieces (agent loop, retrieval fusion, eval metrics, loop-detection prompt), offer to let the user write a first version and then review it. Don't force this; offer it.
6. **Keep `plan.md` current.** Tick tasks off and note anything that slipped or was cut.

Match the depth of explanation to the concept. Spend more on ideas that will come up in interviews (agents, retrieval, evals, prompt injection, privacy and storage) and less on boilerplate.

## Scope guardrails

In scope: single user, Apple Silicon macOS, English, **Gmail as the only action target**, local storage, one strong demo scenario, a **demo mode a reviewer can run with just a free Gemini key**.

Out of scope unless an ADR says otherwise: screenshots or screen recording of any kind (ADR-005), accounts/auth for our app, billing, sync, Windows/Linux for the app, App Store sandboxing, multi-provider email, mobile, production hardening.

If something isn't needed for the demo, for reproducibility, or for learning, cut it and note the cut in `plan.md`.

## Architecture (target)

```
Swift menu-bar app (app/, native)              Python "brain" (brain/, Docker or uv)
├─ Capture: Accessibility API reads    ──►     FastAPI on 127.0.0.1:8765
│  focused app/window text (no pixels)         ├─ ingest → redact → store observations
├─ Inbox UI: open loops, "Close it",   ◄──►    ├─ memory: SQLite + FTS5 + sqlite-vec
│  draft review, approve/send                  ├─ loops: detect → dedupe → lifecycle
└─ Settings: pause, excluded apps,             ├─ agent: Gemini function-calling loop
   delete all, data disclosure                 └─ mailbox: Gmail API | FakeMailbox (demo)
                                                         │ TLS, stateless calls
~/Library/Application Support/ContextAgent/              ▼
  brain.db  ← the only persistent store         Gemini API (LLM + embeddings)
```

- The **brain owns the database.** The Swift app talks to it over HTTP only. It never opens the SQLite file. (ADR-004)
- **Docker can't run the app.** Docker on macOS is a Linux VM with no access to macOS APIs. Docker runs the brain, and the app always runs natively. (ADR-018)
- Planned layout: `app/` (Xcode project), `brain/` (uv project: `src/brain/{api,db,llm,memory,loops,agent,mailbox}`, `evals/`, `tests/`, `Dockerfile`), `fixtures/` (synthetic screen sessions plus a fake inbox), `docs/`, `docker-compose.yml`, `Makefile`.

## Tech stack (details and reasons in `decisions.md`)

| Layer | Choice |
|---|---|
| Native app | Swift 6 + SwiftUI `MenuBarExtra` |
| Capture | macOS Accessibility API (`AXUIElement`) only. **No screenshots, no OCR** |
| Brain | Python 3.12+, `uv`, FastAPI, Pydantic v2, pytest |
| LLM | Gemini via the official `google-genai` SDK. `gemini-3.8-flash` by default |
| Embeddings | `gemini-embedding-2` at 768 dimensions, vectors stored locally |
| Storage | SQLite (WAL) + FTS5 + `sqlite-vec`, one file on the Mac |
| Actions | Gmail API (OAuth installed-app flow). `FakeMailbox` in demo mode |
| Run | `docker compose` (brain) + native app. `DEMO_MODE=1` for reviewers |
| v2 | MCP server exposing memory and loops |

## Gemini API conventions (checked 2026-10-24; the API changes fast, so check the live docs before assuming)

- **Only stable model IDs:** `gemini-3.8-flash` (default) and `gemini-3.5-flash-lite` (pre-filter candidate, decided in Phase 4). Never `-preview` IDs, because they get shut down and would break the demo. Pro models are paid-only, so don't use them.
- All model calls go through `brain/src/brain/llm/client.py`. No other module imports `google.genai`.
- **Stateless calls only.** Don't use server-side conversation state (`previous_interaction_id` or stored interactions). Keep history locally, and pass thought blocks or signatures back **exactly** as received.
- Thinking is controlled with `thinking_level` (low/medium/high on 3.8 Flash, default medium). Set it explicitly per call site.
- Structured output: pass a Pydantic model's JSON Schema as the response format, then **always** `model_validate_json` the result.
- Function calling: our own loop, with the SDK's automatic function execution turned off. We run every tool ourselves (ADR-011).
- Embeddings: `gemini-embedding-2`, `output_dimensionality=768`, **one text per call** (a list gives back one combined vector). No `task_type`. Use the prefixes `task: search result | query: …` and `title: … | text: …`. Cache by content hash.
- Free-tier rate limits are low. Retry 429s with exponential backoff and jitter, and cache responses in evals and tests.
- Before writing new SDK code, read the current page on ai.google.dev (interactions, structured output, function calling, embeddings). Don't write from memory.

## Safety and privacy rules (never break these, even in demo code)

- **No email is sent without an explicit human click.** The model can draft. Only a user action in the UI triggers `send`. The send endpoint must refuse calls that don't come from an approval.
- **Captured screen text and email bodies are untrusted data, not instructions.** Wrap them in delimiters in prompts and tell the model they are data. The agent may only use allowlisted tools, and recipients must already be in the thread.
- **Every agent action goes into an audit log** (`actions` table): tool, inputs, outputs, who approved it, when.
- **Free-tier Gemini is for synthetic and test data only.** Google may use free-tier content and have humans review it (ADR-014). Live capture of real screens needs `GEMINI_TIER=paid`, and the app shows a warning otherwise.
- Redact obvious secrets (API keys, card numbers, OTPs) before storing anything **and** before any API call. The capture denylist covers password managers, banking, and System Settings.
- Nothing persistent leaves the Mac. The brain's port binds to `127.0.0.1` only, including in Docker port mappings.
- Secrets live in `.env` (gitignored) or the macOS Keychain. Never commit API keys, OAuth tokens, `brain.db`, or real personal data. Fixtures are synthetic.

## Commands

_Fill in as they come to exist._

```bash
# reviewer path
cp .env.example .env               # add GEMINI_API_KEY
docker compose up                  # brain on 127.0.0.1:8765 (DEMO_MODE=1 by default)
make app                           # build and launch the native menu-bar app
docker compose run brain demo      # headless end-to-end demo in the terminal

# dev path
cd brain && uv sync
uv run fastapi dev src/brain/api.py
uv run pytest                      # uses recorded LLM responses, no key needed
uv run python -m evals.run_retrieval
```

## Where things are tracked

- `plan.md`: phases, tasks, current status. **Current phase: Phase 0.**
- `decisions.md`: ADRs, meaning every decision with its options and tradeoffs.
- `learnings.md`: concept notes and interview prep, appended after each task.
- `readme.md`: public pitch plus the reviewer quickstart (rewrite in Phase 7).
