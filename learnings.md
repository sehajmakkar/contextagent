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

## Log: what we actually learned

_Newest first. Add entries as tasks finish._

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
