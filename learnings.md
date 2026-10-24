# Learnings

Your study guide and interview prep, written as we build. Each entry covers one concept: what it is, how it works, where it lives in **our** code, what surprised us, and the interview questions it prepares you for.

**How this file grows.** After every task, Claude adds or extends an entry (see the teaching protocol in CLAUDE.md). The primer below gives the core ideas up front. The log at the bottom records what we actually ran into. Rewrite any entry in your own words once you understand it, because explaining it yourself is how it sticks.

### Entry template

```
### <Concept>  (Phase N · links: ADR-x, file:line)
What: one or two sentences, plain language.
How it works: the mechanism, with a tiny example.
In our project: where and why we use it.
Gotchas: what went wrong or surprised us.
Interview Q: "..."  →  short answer.
```

---

## Concept map by phase

| Phase | Concepts |
|---|---|
| 0 | Open loops · local-first · **where your data lives** · free vs paid API tiers · LLM basics (tokens, context window, why calls stop) |
| 1 | LLM request anatomy · system instructions · structured outputs · prompt iteration · rate limits and backoff · Docker basics · record/replay tests |
| 2 | TCC permissions · accessibility tree · why AX text instead of pixels · dedupe and hashing · PII redaction |
| 3 | Embeddings (API-computed, stored locally) · cosine similarity · dimensionality · chunking and episodes · BM25 · hybrid search · RRF · Recall@k and MRR · embedding versioning |
| 4 | Classification vs extraction · cascades · LLM-as-judge · entity resolution · state machines · precision vs recall |
| 5 | Agents vs workflows · tool use · the agent loop · human-in-the-loop · prompt injection · OAuth 2.0 · idempotency · tracing |
| 6 | Streaming (SSE) · trust UX |
| 7 | Eval reporting · threat modelling · telling the story |
| 8 | MCP (tools, resources, transports) |

---

## Primer: the core ideas

### Open loops  (Phase 0 · ADR-001)
**What:** something that was started and not finished. A promise you made ("I'll send it by Wed"), an ask you received, or a follow-up you owe.
**How it works:** detecting a loop means extracting a *commitment* (who owes what to whom, by when) from messy text. Closing it means finding *evidence* that it was done.
**In our project:** Minimi finds loops and marks them resolved when it sees they're done. We add an agent that does the work to close them.
**Interview Q:** "Why do false positives matter more than misses here?" → Every false loop interrupts the user and erodes trust in the inbox. A missed loop is no worse than not having the tool.

### Where your data lives: our storage and privacy design  (Phase 0 · ADR-005, 007, 014, 018, 020)
**The one-sentence version:** everything is *stored* on your Mac, and text only leaves it briefly, encrypted in transit, when Gemini has to *compute* something (an embedding or an LLM answer). Nothing comes back to be stored anywhere except your Mac.

**What's stored, and where:**

| Data | Where | Notes |
|---|---|---|
| Captured screen text (redacted) | `brain.db` → `observations` | Text from the AX tree only. Pixels are never captured |
| Memories (summaries + provenance) | `brain.db` → `memories` + FTS5 index | Keyword index is built locally |
| Embedding vectors (768 floats each) | `brain.db` → `memory_vectors` (sqlite-vec) | The vector *index* is local, which is Minimi's "local vector database" |
| Open loops, evidence, agent audit log | `brain.db` → `loops`, `loop_evidence`, `actions` | |
| Gmail OAuth token | Keychain (target) or a `0600` file in the data folder (prototype) | Never in git |
| Gemini API key | `.env` (gitignored) | |

All of it sits in one folder: `~/Library/Application Support/ContextAgent/`. "Delete all data" deletes that folder. With Docker, the folder is **bind-mounted** into the container, so the data is still a normal folder on the Mac. Deleting or rebuilding the container doesn't touch it, and the container itself holds nothing.

**The journey of one memory:**
```
AX text on screen ─► Swift app ─► brain (localhost) ─► redact ─► SQLite   (on the Mac)
                                                    │
                               memory text ─TLS────►│ Gemini embedding API  (computes, returns 768 floats)
                                                    ◄── vector ─► sqlite-vec   (on the Mac)
Later, a search:  query ─TLS─► Gemini (embed query) ─► vector ─► nearest neighbours searched LOCALLY
                  top few snippets ─TLS─► Gemini LLM (reasons over them) ─► answer back to the Mac
```

**What Minimi's three promises mean in engineering terms:**
- *"Stored on your Mac… local vector database."* The database file is on disk on your machine. That's us too (SQLite + sqlite-vec).
- *"Embeddings via Gemini… on a paid plan. Google doesn't train on or retain this data."* The text **does** go to Google to be embedded. The privacy promise depends on the **paid tier's terms**, not on technology. On the free tier, Google may use the content and humans may review it. That's why our free tier is for synthetic data only (ADR-014).
- *"Encrypted in transit… decrypted only for the moment it's processed."* That's TLS (HTTPS) on the way out and back, plus encryption at rest on the device. The model has to see plaintext to compute anything, so "decrypted for the moment" is the honest phrasing. Our equivalent: TLS is automatic with the SDK, and at rest we rely on FileVault plus file permissions for now, with SQLCipher as a Phase 7 option.

**Subtle points interviewers like:**
- **Embeddings aren't anonymous.** Research shows text can be partly reconstructed from embeddings ("embedding inversion"). Treat vectors as just as sensitive as the text.
- **Stateless calls.** Some APIs offer to keep your conversation on their servers (Gemini's `previous_interaction_id`). We don't use that, so conversation state also stays on the Mac.
- **Redaction happens twice**, before storing and before any API call. Anything that never leaves the Mac can't leak from Google's side.
- **Localhost binding.** The brain listens only on `127.0.0.1` (including the Docker port mapping), so other machines on your Wi-Fi can't query your memory.

**Interview Q:** "You say local-first, but you call a cloud API. Isn't that a contradiction?" → Local-first means the durable copy and the control are yours. Storage, the index, and search run locally. Cloud inference is transient and minimal. I can tell you exactly which bytes leave, on which tier, and I have a strict mode (local models) on the roadmap.
**Interview Q:** "Why not encrypt the DB?" → FileVault already encrypts the disk. App-level encryption (SQLCipher) protects against other processes and backups. It's in Phase 7, pending sqlite-vec compatibility.

### Free vs paid API tiers  (Phase 0 · ADR-014, 019)
**What:** the same Gemini API, under different data terms. Free (unpaid) content can be used to improve Google's products and may be human-reviewed. Paid content (a Cloud project with active billing) isn't used that way and is only logged briefly for abuse checks.
**In our project:** we develop and demo on the free tier with synthetic data only. Real-screen capture expects `GEMINI_TIER=paid`, and the app warns otherwise.
**Gotchas:** free-tier rate limits are low, so we need backoff, caching, and a cheap pre-filter.
**Interview Q:** "How did you keep costs at zero without compromising privacy?" → Free tier for synthetic dev and demo data, paid tier for real data, and caching so that nothing is sent twice.

### Tokens, the context window, and why calls stop  (Phase 0–1)
**What:** LLMs read and write *tokens* (word pieces). The context window is the most tokens one request can hold. On paid tiers, you pay per input and output token.
**How it works:** with stateless calls, every request resends the conversation, because the model keeps no memory between calls. Each response says why generation stopped: it finished, it hit the output-token limit, it wants you to run a function, or it was blocked by safety filters. Always check that before using the output.
**In our project:** we log tokens for every call, and we send only the snippets a step needs. That's cheaper, it uses less rate limit, and it's more private.
**Interview Q:** "With a 1M-token window, why not send everything?" → Cost, latency, rate limits, privacy, and quality. Irrelevant context distracts the model. Retrieval beats dumping.

### Structured outputs  (Phase 1 · ADR-010)
**What:** forcing the model's reply to match a JSON Schema, which we write as a Pydantic model.
**How it works:** pass `Model.model_json_schema()` as the response format with an `application/json` MIME type. The API constrains generation to that shape, and `Model.model_validate_json(text)` gives a typed object or a clear error.
**In our project:** loop candidates, memories, and judge verdicts.
**Gotchas:** if a field is required but unknowable, the model will invent a value. Make it nullable and add `confidence`. Validate even when the API constrains the output.
**Interview Q:** "How do you get reliable JSON from an LLM?" → Use schema-constrained structured outputs, not prompt pleading plus regex. Then validate at the boundary.

### Embeddings and vector search  (Phase 3 · ADR-020)
**What:** an embedding model maps text to a vector, so that texts with similar meaning end up close together (measured by cosine similarity).
**How it works:** embed each memory once and store the vector. At query time, embed the query and find its nearest neighbours.
**In our project:** `gemini-embedding-2` computes 768-dimension vectors, which are stored and searched locally in sqlite-vec. Google trains these models so the first N dimensions still work on their own ("Matryoshka" truncation), which is why 768 out of 3072 works well.
**Gotchas:** no `task_type` on this model, so use text prefixes instead. A list input gives back *one* combined vector. Save the model name with each vector, because changing the model means re-embedding everything, since vectors from different models can't be compared.
**Interview Q:** "When does vector search fail?" → Exact tokens such as names, IDs, and numbers. "Q3" and "Q4" look almost identical as vectors. That's why we use hybrid search.

### BM25, hybrid search, and RRF  (Phase 3 · ADR-009)
**What:** BM25 is classic keyword ranking (term frequency, inverse document frequency, and a length adjustment). Hybrid search runs keyword and vector search and merges the results.
**How it works:** Reciprocal Rank Fusion scores each document as `Σ 1/(k + rank_i)` across the result lists (k≈60). It uses only ranks, so it doesn't care that BM25 scores and cosine scores are on different scales.
**Interview Q:** "Why RRF instead of averaging scores?" → The scores aren't on comparable scales. Rank fusion is robust and needs no tuning.

### Evals  (Phase 3–5 · ADR-015)
**What:** a fixed, labeled test set plus a script that scores the system, so you can tell whether a change helped.
**Metrics:** Recall@k (did the right item appear in the top k?), MRR (how high up the first right item was), precision, recall, and F1 for loop detection, and a rubric-based success rate for agent tasks (judged by an LLM and checked by you).
**Interview Q:** "How do you know your prompt change helped?" → Re-run the eval and compare. For small sets, report counts as well as percentages, and spot-check the judge.

### Agents vs workflows, and the agent loop  (Phase 5 · ADR-011)
**What:** a *workflow* is a series of LLM calls where your code decides the steps. An *agent* is a loop where the model decides which tool to call next, until it's done.
**How it works:** send the history plus function declarations. If the response contains `function_call`s, run them yourself, append the model's turn **unchanged** (including thought signatures) and then all the function results, and call again. Stop when there are no more calls, or when you hit a step or token limit.
**In our project:** detection and memory are workflows, because they're predictable. "Close this loop" is an agent, because which thread to find and what facts to pull vary each time.
**Interview Q:** "When shouldn't you use an agent?" → When the steps are known in advance. Agents cost more, take longer, and are harder to test.

### Prompt injection and human-in-the-loop  (Phase 5 · ADR-012)
**What:** text the agent *reads* (an email, a webpage) contains instructions, and the model follows them.
**How it works:** the dangerous combination is reading untrusted content, having access to private data, and being able to send data out. Any two are manageable. All three are an exfiltration risk.
**In our project:** we remove *autonomous* outward communication. The model drafts and a human sends. We also allowlist tools, restrict recipients, and keep an injection regression test.
**Interview Q:** "Can a better system prompt fix injection?" → Not reliably. Design the permissions so a successful injection can't do damage.

### MCP (Model Context Protocol)  (Phase 8 · ADR-016)
**What:** an open protocol that lets AI apps (Claude, ChatGPT, IDEs) call tools and read resources exposed by a server.
**In our project:** a v2 layer so other assistants can query memory and loops. Minimi's "Memory MCP" is the same idea.
**Interview Q:** "MCP vs a REST API?" → MCP is a standard way to describe tools so any compatible client can discover and call them. Underneath, it's still an API.

---

### Docker on macOS  (Phase 1 · ADR-018)
**What:** Docker packages an app and its dependencies into an image, so it runs the same on any machine.
**How it works on a Mac:** containers need a Linux kernel, so Docker Desktop runs a small **Linux VM**, and containers run inside it. That means a container can't call macOS APIs: no Accessibility, no menu bar, no Keychain.
**In our project:** the Python brain runs in Docker, and the Swift app runs natively and talks to it over `127.0.0.1:8765`. Data lives in a bind-mounted folder on the Mac.
**Gotchas:** inside the container, the server must bind to `0.0.0.0`, while the *host* mapping must be `127.0.0.1:8765:8765`. Otherwise it's reachable from your LAN. You need images built for arm64 (Apple Silicon), so check that sqlite-vec has a linux/arm64 wheel.
**Interview Q:** "Why not put the whole thing in Docker?" → Docker on macOS is Linux in a VM, and screen-text capture needs macOS APIs. So the AI service is containerized for reproducibility, and the OS-facing part stays native.

### Model lifecycle: preview vs stable  (Phase 0 · ADR-019)
**What:** providers ship `-preview` models first and shut them down later. Stable IDs stick around longer.
**In our project:** only stable IDs (`gemini-3.8-flash`, `gemini-3.5-flash-lite`). `gemini-3-pro-preview` has already been shut down. If our demo pinned it, it would break for every reviewer.
**Interview Q:** "How do you guard against model deprecations?" → Pin stable IDs in config, keep all model calls behind one client module, and re-run the evals before switching models.

---

## Phase 1: what we built and why it works

### Anatomy of one LLM call  (Phase 1 · ADR-021 · [client.py](brain/src/brain/llm/client.py))
**What:** every call to the model is one HTTP request: *instructions + input + output contract*, sent to `models.generate_content`.
**How it works, piece by piece:**
- `system_instruction`: the standing rules (role, definitions, what to ignore). It's the same for every observation.
- `contents`: this request's specific input (the capture time, the app, the screen text).
- `response_mime_type` + `response_json_schema` ([client.py:64](brain/src/brain/llm/client.py#L64)): the output contract (see *Structured outputs*).
- `thinking_config.thinking_level`: how much the model reasons privately before answering. Thinking tokens are billed and use up rate limit, so we use `low` for extraction and `medium` for writing emails.
- `store=False` ([client.py:67](brain/src/brain/llm/client.py#L67)): asks Google not to log this request.
- The response's `finish_reason` ([client.py:75](brain/src/brain/llm/client.py#L75)) must be `STOP`. `MAX_TOKENS` means the JSON was cut off, and `SAFETY` means it was blocked. Check it *before* parsing.
- `usage_metadata` gives prompt, output, and **thinking** tokens. The CLI prints totals after each command, so you can watch the cost.
**Interview Q:** "What's the difference between the system prompt and the user prompt?" → The system prompt is the stable policy, the same for every call, which also makes it cacheable. The user prompt is the per-request data. Keeping untrusted data out of the system prompt is a security boundary.

### Prompt patterns in the detection prompt  (Phase 1 · ADR-025 · [detect.py:38](brain/src/brain/loops/detect.py#L38))
- **Definitions with counterexamples.** We spell out what is *not* a loop (pleasantries, marketing, code TODOs, other people's tasks). Models over-detect without negative examples.
- **A base-rate hint.** "Most screens contain no open loops." Without it, the model tends to find *something* on every screen.
- **Date grounding.** We pass the capture time *with the weekday* (`strftime("%A …")`, [detect.py:74](brain/src/brain/loops/detect.py#L74)), so "by Wednesday" becomes `2026-10-21`. The model can't know "today" otherwise.
- **Delimiting untrusted data.** Screen text goes inside `<screen_text>…</screen_text>`, and the rules say it's data, not instructions. This is the first, weakest layer of prompt-injection defence. The real defence is in permissions (ADR-012).
- **Schema field descriptions act as instructions too.** `Field(description=…)` on `LoopCandidate` reaches the model inside the JSON Schema.
**Interview Q:** "How do you stop an extractor from hallucinating?" → Clear negative examples and a base-rate hint, then verify the output in code (the next entry).

### Grounding checks and confidence thresholds  (Phase 1 · ADR-025 · [detect.py:89](brain/src/brain/loops/detect.py#L89))
**What:** treat LLM output as a *claim* to verify, not as fact.
**How it works:** (1) the `evidence_quote` must actually appear in the source text, after normalizing whitespace and case. If it doesn't, the model paraphrased or made it up, so we drop the loop. (2) Below `MIN_CONFIDENCE = 0.6`, we drop it. (3) After drafting, any recipient address not in the thread is removed ([draft.py:70](brain/src/brain/agent/draft.py#L70)).
**Gotchas:** a model's self-reported confidence isn't *calibrated* (0.8 doesn't mean right 80% of the time). The threshold is a guess until the Phase 4 eval measures precision and recall at different cut-offs.
**Interview Q:** "Why ask for a verbatim quote?" → It makes the claim checkable with one string search, and it gives the UI proof to show the user.

### Idempotent ingest, content hashes, and transactions  (Phase 1 · ADR-022 · [store.py](brain/src/brain/db/store.py))
**What:** *idempotent* means running something twice gives the same result as running it once.
**How it works:** each observation gets `sha256(bundle_id, window_title, text)` ([store.py:47](brain/src/brain/db/store.py#L47)), with a `UNIQUE` constraint and `INSERT OR IGNORE`. Re-ingesting the file stores nothing new (the test proves it). Detection runs in a **separate pass** over `processed_at IS NULL`. If Gemini fails midway (a 429 or a timeout), `brain detect` picks up exactly where it stopped. Each observation's loops and its `processed` flag are written in **one transaction** ([cli.py:97](brain/src/brain/cli.py#L97)), so a crash can't leave half-written state.
**Gotchas:** our first version detected inside the insert loop, so a failed observation was stored but never retried, because re-ingesting skipped it as a duplicate. Splitting "store" from "process" fixed it.
**Interview Q:** "Your capture app retries a POST. How do you avoid duplicates?" → A content hash plus a unique constraint makes ingest idempotent. Processing state lives in the row, not in memory.

### Retries, exponential backoff, and jitter  (Phase 1 · [client.py:43](brain/src/brain/llm/client.py#L43))
**What:** when an API says "too many requests" (429) or has a server error (5xx), wait and try again, longer each time.
**How it works:** delay ≈ `initial_delay × 2^attempt` (2s, 4s, 8s…, capped at 60s), plus random **jitter**, so many clients don't all retry at the same instant (the "thundering herd"). The SDK's `HttpRetryOptions` does this for 408/429/5xx. We set 5 attempts. If they're all used up, we raise `LLMError`.
**Gotchas:** retrying doesn't help when the *daily* free quota is gone, only when the per-minute limit was hit. Never retry 400s, since the request itself is wrong.
**Interview Q:** "Why jitter?" → Without it, clients that failed together retry together and overload the server again.

### SQLite details that matter  (Phase 1 · ADR-022)
- **WAL mode** (`PRAGMA journal_mode=WAL`): readers don't block the writer. That matters once the Swift app reads loops while the brain writes.
- **`PRAGMA user_version`**: a free integer in the DB header that we use as the schema version, so migrations run once.
- **`foreign_keys=ON`**: SQLite turns it off by default. Without it, `ON DELETE CASCADE` does nothing.
- **Permissions**: DB file `0600`, folder `0700`, so other user accounts on the Mac can't read it.

### Redaction and the Luhn check  (Phase 1 · [redact.py](brain/src/brain/redact.py))
**What:** regex patterns for well-known secret shapes (Google/OpenAI/AWS/GitHub/Slack keys, PEM private keys, OTP codes), applied before storing.
**How it works:** a 13–19 digit run is only redacted as a card if it passes the **Luhn checksum** ([redact.py:24](brain/src/brain/redact.py#L24)), the check digit every real card number has. This keeps order numbers and IDs from being wiped out.
**Gotchas:** regexes catch known shapes only. It's a safety net, not a guarantee, so it's layered with the app denylist (Phase 2) and the free-tier rule.

---

### Output encoding: model output is untrusted when you *display* it too  (Phase 1 · [cli.py](brain/src/brain/cli.py))
**What:** text from the screen or the model can contain characters that the *display layer* treats as code. On the web that's XSS (HTML). In our terminal, it's Rich's `[style]` markup.
**What happened:** the draft said `[[available times next week]]`, and Rich parsed `[available times next week]` as a style tag and swallowed it, so the user saw `[]`. `[[Q3 retention numbers]]` survived only because it starts with a capital letter. Our own `[created]` label vanished the same way.
**Fix:** escape every untrusted string at the point of display (`_e()` → `rich.markup.escape`), with a regression test in `tests/test_cli.py`. The SwiftUI app in Phase 6 must treat model text as plain text, never as Markdown or attributed strings.
**Interview Q:** "Where do you sanitise LLM output?" → At every boundary where it's interpreted: as SQL (parameterised queries), as HTML or markup (escaping), as shell (never), and as tool arguments (schema validation plus an allowlist).

### Scaling actions to many apps: connectors, tools, and risk-based approval  (Phase 5 preview · ADR-026)
**The question:** today `agent/draft.py` drafts one Gmail reply. How does a company like Minimi close loops across WhatsApp, docs, PDFs, research, and email?
**The pattern most agent products converge on:**
1. **Separate the brain from the hands.** One *planner* agent decides how to close the loop. Many *tools* do the work. The agent never contains Gmail-specific logic. It sees tool descriptions and schemas, then picks tools.
2. **A connector exposes typed tools**, each declaring `name`, `description`, a JSON Schema, and a **risk class**:
   - `read`: search memory, fetch a thread, read a doc (no side effects)
   - `draft`: create a draft, create a doc in a drafts folder (reversible, private)
   - `execute`: send, post, share, pay (outward, irreversible)
3. **Approval policy keys on risk class, not on the app.** `read` runs freely, `draft` runs and shows its result, and `execute` *always* needs a human click. Adding WhatsApp doesn't mean new safety code, only a new connector whose `send` is tagged `execute`.
4. **Plan → approve → execute → verify.** The agent proposes a structured plan ("reply in the WhatsApp chat where the ask came from, attaching the PDF I'll generate"). The user approves. Tools run. Then a verify tool reads the result back (is the message in Sent, does the file exist) before the loop closes.
5. **The reply channel follows the source.** The loop's evidence says where the ask came from (Gmail thread, Slack DM, WhatsApp chat), and that's usually where the reply goes.
**How companies get the "hands" (from best to most fragile):**
- **Official APIs** (Gmail, Slack, Notion, Google Docs): reliable and scoped, but each one needs OAuth, token refresh, and maintenance. Many companies buy this layer from integration platforms (Composio, Nango, Pipedream Connect, Merge, Paragon) instead of building 50 OAuth flows themselves.
- **MCP servers:** the emerging standard. The agent is an MCP *client*, and each app is an MCP *server* exposing tools. Many vendors now ship their own. One protocol means N integrations without N custom adapters.
- **OS-level automation on the Mac:** App Intents, Shortcuts, AppleScript, and URL schemes. For example, a WhatsApp deep link can open the chat with the text pre-filled, and the user presses Send. Human-in-the-loop comes for free.
- **UI automation through Accessibility:** the same AX API we *read* with can also *press buttons and type*. It covers apps with no API (personal WhatsApp has no official API), but it breaks when the UI changes.
- **Computer use (vision models clicking pixels):** the most general and the most fragile. We ruled out screenshots (ADR-005).
**"Producer" tools** (make a PDF, write a doc, do research) are just tools that create an *artifact* (a local file or a doc in drafts). Sending that artifact is a separate `execute` step that goes through approval.
**At scale:** with hundreds of tools, models choose worse, so the agent retrieves only the relevant tools per loop ("tool search"). Every tool gets its own eval, and every `execute` gets an idempotency key so a retry never sends twice.
**Interview Q:** "How would you take this from Gmail to 20 integrations?" → A connector interface with risk-classed tools, a generic approval gate keyed on risk, MCP or an integration platform for auth, and plan → approve → execute → verify, so adding an app is configuration, not new safety logic.

---

## Log: what we actually learned

_Newest first. Add entries as tasks finish._

### 2026-10-25: First live run of Phase 1 (verification)
- **Detection vs the answer key** (`fixtures/README.md`): 6 expected loops, **5 found, 0 false positives, 1 miss.** Precision 5/5 = 1.00, recall 5/6 = 0.83.
  - ✅ Priya (due 2026-10-21: it used *your* "by Wednesday", not her "before Thursday"), Rahul PR, Maya, Ananya (*they owe*, due Friday 10-23), lease (10-31).
  - ✅ Ignored the promo email, the coffee pleasantry, the code TODO, the already-sent NDA, and Dev's and Priya's action items.
  - ✅ Dedupe: the second visit to the Priya thread attached to loop #1 ("Seen 2×") instead of creating a duplicate.
  - ❌ **Missed:** "Sehaj: write the launch blog post draft by Oct 28" in the meeting notes. Likely cause: our rule "tasks that involve no other person are not loops" makes a meeting action item look like a to-do for yourself. **This is your first prompt-iteration exercise.**
  - ⏳ Expected for Phase 1: the PR loop stays open even though Rahul later said "merged". Closure detection is Phase 4.
- **Cost and latency:** 15 calls, 7,376 prompt tokens, 726 output, **1,915 thinking**, 54.8s total (about 3.7s per call). Thinking at `low` still varies: the meeting-notes call used 1,183 thinking tokens and took 13s, *and* missed the loop. Hard inputs cost more.
- **Rate-limit maths for Phase 2:** at one observation every 30s, per-observation detection is about 120 calls an hour, which would use up a daily free quota within a working day. That's why Phase 2 needs dedupe and throttling, and Phase 4 needs a cheap pre-filter.
- `store=False` is accepted on the free tier (ADR-021 risk resolved).
- Re-ingesting is idempotent: 0 new, 15 duplicates, 0 LLM calls.
- **Bug found and fixed:** Rich markup injection in the CLI (see *Output encoding*).
- Added `thinking_tokens` to the audit log, because thinking was the largest token cost on some calls.

### 2026-10-24: Building the Phase 1 walking skeleton
- We read the installed SDK source (`google-genai` 2.33.0) instead of relying on blog posts. That's how we found that `generate_content` isn't deprecated, has a `store` flag, and has built-in retry options. Third-party pages disagreed about model names and APIs. The source was the ground truth.
- Bug caught in design review: detecting during insert made failed observations impossible to retry. The fix was to split store from process (see *Idempotent ingest*).
- The fixtures double as a labelled eval set (answer key in `fixtures/README.md`). Writing tricky negatives (promo email, coffee pleasantry, code TODO, other people's action items) is half of prompt design.
- Still to do with your key: run live, compare against the answer key, and log the first prompt iteration here.

### 2026-10-24: Switching from Claude to Gemini, and the reviewer-ready design (Phase 0)
- We switched the LLM and embeddings to Gemini for the free tier (ADR-019 and 020 replace ADR-006 and 008). The decision history stays in `decisions.md`.
- Lesson: the free tier is free because your data helps train Google's models. "Free" and "private" pull in opposite directions, so we split them: free tier for synthetic data, paid tier for real data.
- Lesson: Gemini's current docs lead with an Interactions API that can store conversation state on Google's side. We choose stateless calls to keep state local, which is a privacy decision as much as a technical one.
- Lesson: `gemini-embedding-2` has quirks (prefixes instead of `task_type`, a list giving one combined vector, auto-normalization). Read the docs before writing code.
- Lesson: "make it run anywhere" ran into an OS limit. Docker can't reach macOS APIs, so the design became Docker brain, native app, and demo mode.

### 2026-10-24: Researching Minimi (Phase 0)
- Minimi's site describes capture through Apple's accessibility infrastructure ("we don't take screenshots"). Memory is stored as embeddings in a local vector DB. Inference goes to cloud providers through Minimi's backend (Gemini for embeddings, OpenAI for action items and decision-tracing, Deepgram for audio). They offer a Memory MCP plus an "Open loops Inbox".
- Lesson: "local-first" in this space usually means *storage* stays local while *inference* runs in the cloud. Our ADR-014 takes the same approach but goes further by doing embeddings locally.
- Lesson: their accessibility-first capture is why ADR-005 picks AX over screenshots.
