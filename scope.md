# DevRecall
### A local-first memory and context engine for macOS

> Your AI should remember what you're working on, what you've already tried, and what still needs to be done.

DevRecall is a privacy-first, developer-centric personal context engine for macOS. It builds a searchable memory of your work across desktop applications, understands ongoing tasks, tracks open and completed loops, and exposes relevant context to AI assistants through the Model Context Protocol (MCP).

Instead of repeatedly explaining your project, decisions, preferences, and unfinished work to an AI assistant, DevRecall gives compatible agents access to the context they need to help you continue where you left off.

**The vision:** An always-available, local-first memory layer that makes AI assistants genuinely aware of your ongoing work.

> **Project status:** Early-stage concept / development. Features and architecture described below are planned and subject to change.

---

## Table of Contents

- [The Problem](#the-problem)
- [The Solution](#the-solution)
- [Core Features](#core-features)
- [How It Works](#how-it-works)
- [Privacy-First Architecture](#privacy-first-architecture)
- [Proposed Tech Stack](#proposed-tech-stack)
- [System Architecture](#system-architecture)
- [MCP Integration](#mcp-integration)
- [Open and Closed Loop Tracking](#open-and-closed-loop-tracking)
- [Evaluation and Metrics](#evaluation-and-metrics)
- [Development Roadmap](#development-roadmap)
- [Target Companies and Ecosystem](#target-companies-and-ecosystem)
- [Design Principles](#design-principles)
- [Future Possibilities](#future-possibilities)
- [Contributing](#contributing)

---

## The Problem

AI assistants are powerful, but most interactions still suffer from fragmented context.

- **Lost context:** An AI assistant may not know what you were doing in another application or in yesterday's session.
- **Repeated explanations:** Developers repeatedly explain their architecture, codebase, decisions, constraints, and preferences.
- **Forgotten open loops:** Unfinished tasks, pending decisions, follow-ups, and unresolved issues get buried across apps.
- **Fragmented memory:** Useful context is scattered across terminals, code editors, browsers, documentation, meetings, and notes.
- **Context-window waste:** Users often need to provide excessive history because relevant information cannot be retrieved reliably.
- **Privacy concerns:** Sending entire activity histories, screenshots, or personal documents to cloud services is undesirable.

What is missing is a persistent context layer between the user's everyday work and the AI assistants they use.

## The Solution

DevRecall creates a personal, searchable memory of work on the Mac.

It observes permitted work context, extracts useful information locally, organizes memories around projects and tasks, and identifies unresolved or completed work. Users can inspect and correct this memory, while compatible AI agents can retrieve relevant information through MCP tools.

The system should prioritize useful context over exhaustive surveillance: it should remember decisions, important events, task state, and unresolved questions rather than simply accumulate activity logs.

### Example

You spend Monday debugging an API authentication issue, compare two approaches, settle on one, and leave a follow-up for Tuesday.

On Tuesday, you ask your AI coding assistant:

> "Where did I leave off yesterday, and what should I do next?"

DevRecall retrieves the relevant project context, previous decision, attempted solutions, and open loop. The assistant can resume the work without requiring you to reconstruct the entire session.

---

## Core Features

### 1. Cross-Application Context Capture

Build an understanding of work across the macOS desktop, rather than treating every application as an isolated session.

Potential context sources include:

- Code editors and IDEs
- Terminals and command-line tools
- Web browsers and documentation
- Notes and text editors
- Project management applications
- Meeting and communication tools
- User-created notes and explicit memory saves

The initial implementation should focus on a limited set of reliable sources before expanding to broader desktop coverage.

**Important distinction:** Screenshots are a possible temporary input to local context extraction, not the intended memory format. The system should extract useful text, application metadata, task context, and derived events. Raw screenshots should be discarded by default after processing, unless the user explicitly enables a retention feature.

### 2. Local-First Memory Store

Maintain a structured, searchable store of personal context on the user's Mac.

A memory may contain:

- Content and summary
- Timestamp and source application
- Associated project or workspace
- Memory type and tags
- Links to related memories
- Confidence and provenance
- Retention and sensitivity metadata

Memory types may include decisions, facts, preferences, events, bugs, solutions, tasks, and follow-ups.

Retrieval should initially support keyword search, filters, and recency ranking. Semantic search and hybrid retrieval can be added when evaluation demonstrates their value.

### 3. Automatic Open and Closed Loop Tracking

Identify work that remains unfinished and work that has been completed.

Examples of open loops:

- A bug was identified but not resolved.
- A technical decision still needs to be made.
- A pull request requires review.
- A person needs a response.
- An experiment needs to be run.
- A task was discussed but never completed.

Examples of closed loops:

- A bug was resolved and verified.
- A decision was finalized.
- A follow-up was completed.
- A task was explicitly marked done.

Each loop should have a state, associated project, supporting evidence, timestamps, and optional due date.

The system should distinguish confirmed completion from an inferred completion. Users must be able to correct the status, and uncertain inferences should not silently become facts.

### 4. MCP Server for AI Assistants

Expose personal context through a permission-controlled MCP server.

Compatible AI clients should be able to:

- Search previous work and memories.
- Retrieve recent project context.
- List open loops and pending decisions.
- Recall relevant technical decisions.
- Save a new memory when authorized.
- Mark tasks complete when authorized.
- Request a concise handoff summary for the next session.

Potential tools include `search_memory`, `get_recent_context`, `list_open_loops`, `get_project_context`, `save_memory`, and `update_loop_status`.

The MCP server should return relevant, bounded results rather than dumping the entire memory store into the model context.

### 5. Personal Context and Preferences

Over time, DevRecall may build a user-controlled understanding of recurring preferences and working patterns.

Examples include preferred programming languages, project conventions, recurring workflows, frequently used tools, and explicitly saved personal preferences.

Personal preferences must remain inspectable, editable, and deletable by the user.

### 6. Memory Browser and Control Center

A lightweight macOS interface should let users:

- Search and browse memories.
- View recent activity and project timelines.
- Inspect open and closed loops.
- Correct inaccurate memories.
- Manage excluded applications and capture permissions.
- Delete individual memories or all locally stored context.
- Inspect which context is exposed to AI clients.

The interface should make the memory system understandable and controllable, not hide its behavior behind a black box.

---

## How It Works

1. **Capture:** Collect permitted desktop context or explicitly saved information.
2. **Extract:** Process supported inputs locally to extract text, metadata, and useful events.
3. **Structure:** Convert extracted information into searchable memories and candidate tasks.
4. **Resolve:** Link related events to projects, decisions, and open loops.
5. **Index:** Store memories in a local database and build search indexes.
6. **Retrieve:** Rank relevant memories using keywords, metadata, recency, and eventually semantic similarity.
7. **Provide context:** Return relevant information through the app or an authorized MCP request.
8. **Evaluate and correct:** Measure retrieval quality and let users correct inaccurate or outdated context.

Automatic inference should remain separate from verified facts. A model-generated summary or inferred task status should preserve its source and confidence.

---

## Privacy-First Architecture

Privacy is a core architectural constraint, not a marketing feature.

### Principles

- **Local by default:** Store personal context on the Mac.
- **No cloud dependency for core memory:** Capture, storage, indexing, and basic retrieval should work locally.
- **No screenshot archive by default:** Process permitted screen content locally and discard raw frames after extraction.
- **Explicit permissions:** Let users control supported applications, capture modes, and retention.
- **Visible controls:** Provide pause, exclusion, deletion, and inspection controls.
- **Data minimization:** Retain useful context rather than every observed detail.
- **Transparent provenance:** Show where a memory originated and whether it was inferred.
- **Controlled sharing:** Only provide context to an AI client through an authorized request.
- **Secure storage:** Protect local data and credentials using appropriate macOS security facilities.
- **No silent uploads:** Any future cloud-based model or embedding feature must disclose what data leaves the device and require appropriate consent.

Local storage alone does not guarantee privacy. Logs, temporary files, backups, model requests, and application permissions must also be considered.

### Proposed Storage Model

Use SQLite as the initial persistence layer, with full-text indexing through FTS5.

Potential tables:

- `memories`
- `sources`
- `projects`
- `events`
- `loops`
- `memory_links`
- `user_preferences`
- `capture_policies`

Raw capture artifacts should have a separate, short-lived lifecycle from durable memories. Sensitive content should be excluded or redacted before it is exposed to external models.

---

## Proposed Tech Stack

These are initial recommendations, not fixed requirements.

| Component | Proposed technology |
|---|---|
| Native macOS app | Swift + SwiftUI |
| Screen and window capture | ScreenCaptureKit, with explicit permissions |
| Local OCR and text extraction | Apple Vision |
| Local persistence | SQLite |
| Full-text retrieval | SQLite FTS5 |
| Semantic retrieval | Local or explicitly configured embedding model |
| MCP server | TypeScript + Node.js |
| Validation and schemas | TypeScript + Zod |
| Background processing | Native macOS services and controlled workers |
| Evaluation | Custom benchmark runner and structured result logs |
| Testing | Unit, integration, privacy, and retrieval regression tests |

The first version should minimize dependencies and avoid unnecessary infrastructure. A cloud database, hosted vector store, or external telemetry service should not be required for core functionality.

---

## System Architecture

```text
              macOS Desktop
                    |
       +------------+-------------+
       |            |             |
   Screen/App    Manual Saves   Supported
    Context       and Notes     Integrations
       |            |             |
       +------------+-------------+
                    |
             Local Extraction
          OCR / Text / Metadata
                    |
             Memory Processing
       Summaries / Events / Loops
                    |
             Local Memory Store
             SQLite + FTS5
                    |
          Retrieval and Ranking
       Keywords / Filters / Recency
          + Optional Embeddings
                    |
             Local MCP Server
                    |
       +------------+-------------+
       |            |             |
   Claude Code   Other MCP     Memory UI
                 Clients
```

The capture, processing, storage, and retrieval layers should be modular so each can be tested independently.

---

## MCP Integration

MCP is the interface between DevRecall's local memory and compatible AI assistants.

### Initial Tool Design

| Tool | Purpose |
|---|---|
| `search_memory` | Search memories using a query and optional filters |
| `get_recent_context` | Retrieve a concise summary of recent work |
| `get_project_context` | Retrieve important context for a selected project |
| `list_open_loops` | Find unfinished tasks and pending decisions |
| `get_loop_details` | Retrieve evidence and history for a particular loop |
| `save_memory` | Store user-approved or authorized context |
| `update_loop_status` | Update an open or completed loop |
| `create_handoff` | Generate a structured session-resumption summary |

Tools should use validated inputs, bounded outputs, and explicit authorization for sensitive or modifying operations.

### Example

A developer asks an MCP-compatible coding assistant:

> "Continue the authentication refactor I was working on yesterday."

The assistant can retrieve project context, relevant decisions, recent events, and unresolved loops. It then uses this information to formulate its next steps.

The assistant should not receive unrelated personal history merely because it is available.

---

## Open and Closed Loop Tracking

Open-loop tracking is a central feature, not just a task list.

A loop can be created from an explicit user action or inferred from permitted context.

Example lifecycle:

```text
Observed event
     |
Candidate loop detected
     |
Evidence and confidence checked
     |
User confirmation or safe automatic creation
     |
Open loop
     |
New evidence / progress
     |
Completion verified
     |
Closed loop
```

Potential loop attributes:

- Title and description
- Project and source
- Status
- Created and last-updated timestamps
- Evidence supporting the loop
- Confidence of automatic inference
- Dependencies and related loops
- Due date, when known
- Completion evidence

An implementation should evaluate false positives as carefully as missed loops. An inferred task should not be treated as completed merely because the user stopped discussing it.

---

## Evaluation and Metrics

DevRecall should be evaluated as a retrieval and context-management system, not just a visually impressive app.

Every major capability should have a measurable success criterion, a reproducible test set, and a baseline for comparison.

### 1. Retrieval Quality

| Metric | What it measures |
|---|---|
| Recall@5 | Whether a relevant memory appears in the top five results |
| Precision@5 | How many of the top five results are relevant |
| Recall@10 | Whether relevant memories appear in the top ten results |
| Mean Reciprocal Rank (MRR) | How highly the first relevant result ranks |
| nDCG@k | Quality of ranking when results have graded relevance |
| Retrieval success rate | Percentage of queries that retrieve sufficient context |
| Unsupported retrieval rate | Frequency of results that do not support the requested answer |

Build a labeled benchmark of realistic queries with known relevant memories. Compare keyword search, semantic search, and hybrid retrieval on the same dataset.

### 2. Latency and Performance

| Metric | What it measures |
|---|---|
| Retrieval latency p50 | Median time to retrieve results |
| Retrieval latency p95 | Time within which 95% of retrieval requests complete |
| End-to-end latency p50/p95 | Time from request to usable context |
| Capture processing latency | Time needed to process permitted input |
| Indexing latency | Time required to make new memories searchable |
| Memory footprint | RAM and disk usage |
| CPU usage | Processing overhead during typical use |
| Battery impact | Additional energy use during representative workloads |

Report workload size, hardware, dataset size, and whether semantic indexing is enabled. Establish performance targets after measuring a baseline.

### 3. Open-Loop Detection

| Metric | What it measures |
|---|---|
| Precision / recall / F1 | Quality of detecting unfinished work |
| False-positive rate | Completed or irrelevant work incorrectly marked open |
| False-negative rate | Genuine open loops that were missed |
| Completion detection accuracy | Whether completed work is correctly identified |
| Status transition accuracy | Whether state changes are supported by evidence |
| Time to detection | Delay between a meaningful event and loop creation or update |
| Duplicate loop rate | How often the same task is created repeatedly |

Evaluate against manually labeled sessions and include ambiguous cases, abandoned tasks, reopened bugs, and tasks completed in another application.

### 4. Memory Quality and Freshness

| Metric | What it measures |
|---|---|
| Memory factuality | Whether stored summaries are supported by source evidence |
| Provenance coverage | Percentage of memories with traceable sources |
| Deduplication rate | Reduction in redundant memory entries |
| Staleness rate | Percentage of memories that are outdated or contradicted |
| Update accuracy | Whether new evidence correctly updates existing memories |
| User correction rate | How often users need to fix inaccurate memories |
| Memory deletion effectiveness | Whether deleted content is removed from the relevant storage and indexes |

Memory summaries should preserve uncertainty and distinguish user-confirmed facts from model-generated inferences.

### 5. Agent and Task-Resumption Quality

| Metric | What it measures |
|---|---|
| Task resumption success rate | Whether an agent can continue a task using retrieved context |
| Context sufficiency | Whether the returned context contains the information needed |
| Decision recall | Whether the assistant retrieves relevant prior decisions |
| Next-step accuracy | Whether the suggested next action matches the known task state |
| Context tokens per task | Tokens needed to provide relevant context |
| Tokens saved | Reduction versus supplying the full available history |
| End-to-end task success | Whether the overall task is completed correctly |
| Regression rate | Whether changes to retrieval or memory processing break previously passing cases |

Use the same task set and model configuration when comparing with and without DevRecall. Report task success alongside latency and token usage; fewer tokens do not automatically mean better results.

### 6. Privacy and Security

| Metric | What it measures |
|---|---|
| Unauthorized disclosure tests passed | Whether restricted context stays inaccessible |
| Excluded-app capture violations | Whether excluded applications are ever captured |
| Redaction test pass rate | Whether known sensitive test content is correctly handled |
| Data-egress audit results | Whether unexpected outbound data transfers occur |
| Deletion verification rate | Whether deletion removes applicable records and derived indexes |
| Permission enforcement rate | Whether capture and retrieval respect configured policies |
| Sensitive-content exposure rate | How often protected content appears in unauthorized results |

Test malicious prompt instructions embedded in captured content, cross-project access boundaries, and attempts by an AI client to retrieve excluded information.

### 7. User Experience and Adoption

| Metric | What it measures |
|---|---|
| Time to resume work | Time needed to return to a previous task |
| Manual context reconstruction time | Time spent piecing together previous work without the tool |
| Useful-memory rate | Percentage of stored memories users consider useful |
| Correction / dismissal rate | How often inferred context or loops need correction |
| Search-to-success rate | Percentage of searches that lead to useful context |
| Weekly active usage | Whether users continue to use the product |
| Memory acceptance rate | Whether suggested memories are retained or confirmed |

These metrics require real-user studies or carefully designed usability tests; they should not be presented as proven product benefits until measured.

### Evaluation Methodology

The initial evaluation harness should:

1. Build a small dataset of realistic development sessions and expected memories.
2. Label relevant results and open/closed loop states.
3. Establish a keyword-search and manual-context baseline.
4. Compare retrieval and ranking strategies on the same queries.
5. Measure latency, memory usage, and token consumption.
6. Run regression tests after changes to extraction, ranking, or summarization.
7. Maintain a privacy test suite with sensitive and excluded content.
8. Record results in a reproducible report.

For a first benchmark, target 50–100 representative retrieval queries and expand the dataset as the product grows. These are initial dataset goals, not claims about achieved performance.

---

## Development Roadmap

### Phase 1 — Local Memory Foundation

- [ ] Create the macOS app and project structure.
- [ ] Implement local SQLite storage.
- [ ] Add explicit memory creation and editing.
- [ ] Add full-text search with FTS5.
- [ ] Support projects, timestamps, tags, and source metadata.
- [ ] Build a small retrieval evaluation dataset.
- [ ] Measure baseline retrieval quality and latency.

### Phase 2 — MCP Integration

- [ ] Implement the MCP server.
- [ ] Add `search_memory` and `get_recent_context`.
- [ ] Add project context and open-loop retrieval tools.
- [ ] Validate inputs and limit returned context.
- [ ] Test with Claude Code and other supported MCP clients.
- [ ] Add authorization and tool-level audit logs.

### Phase 3 — Desktop Context Capture

- [ ] Add explicit screen-capture permissions.
- [ ] Support a small set of desktop context sources.
- [ ] Perform text extraction locally.
- [ ] Discard raw frames by default after processing.
- [ ] Add application exclusions, pause controls, and retention policies.
- [ ] Convert extracted events into candidate memories.

### Phase 4 — Automatic Loop Tracking

- [ ] Define a loop schema and lifecycle.
- [ ] Detect candidate tasks and unresolved decisions.
- [ ] Link related events to existing loops.
- [ ] Detect completion using supporting evidence.
- [ ] Allow user confirmation and correction.
- [ ] Evaluate precision, recall, F1, and duplicate rates.

### Phase 5 — Smarter Retrieval and Context

- [ ] Add optional embeddings.
- [ ] Compare keyword, semantic, and hybrid retrieval.
- [ ] Introduce recency-aware ranking and deduplication.
- [ ] Generate project handoff summaries.
- [ ] Add memory freshness and contradiction handling.
- [ ] Evaluate task-resumption success and token savings.

### Phase 6 — Reliability and Release

- [ ] Add end-to-end tests.
- [ ] Run privacy and data-egress audits.
- [ ] Profile CPU, memory, and battery impact.
- [ ] Publish reproducible evaluation results.
- [ ] Document architecture and threat model.
- [ ] Package a usable macOS demo.

---

## Target Companies and Ecosystem

The following companies are potential research, networking, and outreach targets because their products or engineering problems overlap with local memory, desktop AI, agent infrastructure, context retrieval, observability, evaluation, or AI-powered media workflows.

**This is a target list, not a claim that these companies are hiring, that every company is an ideal fit, or that the project is affiliated with them.** Roles, location requirements, funding, and eligibility should be verified independently before applying.

### A. Personal Memory and Desktop Context

Companies whose products are closest to the core product vision.

- [Minimi](https://www.projectminimi.com/) — Local-first personal context and memory for Mac.
- [HeyClicky](https://www.ycombinator.com/companies/heyclicky) — Voice-first, screen-aware desktop AI assistant.
- [Screenpipe](https://github.com/screenpipe/screenpipe) — Local-first searchable computer history and agent context.
- [Sentient OS](https://www.ycombinator.com/companies/sentient-os) — On-device personal AI memory and desktop agents.
- [Pickle](https://builder.pickle.com/) — Personal AI and episodic memory.
- [Nessie](https://www.ycombinator.com/companies/nessie) — Personal context for long-running AI conversations.
- [IrisGo](https://irisgo.ai/careers) — Desktop AI assistant for learning and automating workflows.
- [jo](https://www.ycombinator.com/companies/jo) — Personal AI agent for work and life context.
- [Egoist Machines](https://www.ycombinator.com/companies/egoist-machines) — User-controlled context across AI applications.
- [Crater](https://crater.so/) — Ambient macOS AI assistant.
- [Memory Store](https://www.ycombinator.com/companies/memory-store) — Shared team memory from work tools and conversations.
- [Epicenter](https://www.ycombinator.com/companies/industry/AI%20Assistant) — Open-source, local-first apps with shared context.
- [Almanac](https://www.ycombinator.com/) — Work-context and agent-oriented product research target; verify the specific company and role.
- [Supermemory](https://supermemory.ai/blog/an-update-on-supermemory/) — Memory infrastructure and APIs for AI applications.

### B. Memory Infrastructure and AI Agents

Companies relevant to MCP, agent memory, tool integration, and developer-facing AI infrastructure.

- [Mem0](https://mem0.ai/openmemory) — Persistent memory infrastructure and OpenMemory MCP.
- [Composio](https://composio.dev/) — Tool integrations for AI agents.
- [Metorial](https://metorial.com/) — MCP and agent integration infrastructure.
- [Dexto](https://dexto.ai/) — AI agent development infrastructure.
- [Lyzr](https://www.lyzr.ai/) — Enterprise agent platforms.
- [UnifyApps](https://www.unifyapps.com/) — Enterprise AI and workflow automation.
- [Scalekit](https://www.scalekit.com/) — Authentication and authorization infrastructure relevant to AI applications.
- [TrueFoundry](https://www.truefoundry.com/) — AI infrastructure and deployment.
- [Portkey](https://portkey.ai/) — LLM gateway, observability, and reliability.
- [Maxim AI](https://www.getmaxim.ai/) — AI agent evaluation and observability.
- [Agnost AI](https://agnost.ai/) — AI agent development tooling; verify current product and company details.
- [Ressl AI](https://ressl.ai/) — AI engineering and evaluation tooling; verify current product and hiring status.

### C. AI Evaluation, Testing, and Observability

These companies are relevant to the evaluation harness, tracing, regression tests, and reliability aspects of DevRecall.

- [Athina AI](https://athina.ai/) — LLM evaluation and observability.
- [Cekura](https://www.cekura.ai/) — Testing and evaluation for AI voice agents.
- [BentoLabs](https://bentoml.com/) — AI model serving and deployment ecosystem; verify the specific target entity.
- [DrDroid](https://drdroid.io/) — AI-powered incident investigation and reliability workflows.
- [CodeAnt AI](https://www.codeant.ai/) — AI-assisted code review and software quality.
- [TestMu AI](https://www.testmu.ai/) — AI-enabled software testing.
- [Raga AI](https://raga.ai/) — AI quality, testing, and evaluation.

### D. AI Media and Video Workflows

These companies are useful targets for exploring adjacent problems involving cross-application context, media understanding, and workflow automation.

- [Cardboard](https://www.cardboard.ai/) — AI-powered video editing.
- [Clueso](https://www.clueso.io/) — AI-generated product videos and documentation.
- [Trupeer](https://www.trupeer.ai/) — AI-generated product videos and walkthroughs.
- [InVideo](https://invideo.io/) — AI-assisted video creation.
- [Spyne.ai](https://www.spyne.ai/) — AI-powered visual content workflows.

### E. Broader AI Product and Engineering Benchmarks

These companies are useful for researching product quality, agent workflows, engineering practices, and possible backend or AI engineering opportunities.

- [Granola](https://www.granola.ai/jobs) — AI meeting notes and work context.
- [Town](https://town.com/) — AI coworker and desktop AI; verify current company and role details.
- [Ressl AI](https://ressl.ai/) — Also relevant to evaluation and agent tooling.
- [Maxim AI](https://www.getmaxim.ai/) — Also relevant to agent reliability and testing.

### How to Use This List

Prioritize companies according to:

1. **Product overlap:** Does the team work on local memory, desktop context, agent memory, or retrieval?
2. **Engineering fit:** Can your project demonstrate a relevant capability such as MCP, retrieval quality, or secure local storage?
3. **Role availability:** Is there a real engineering role or an appropriate opportunity for a direct founder outreach?
4. **Hiring feasibility:** Are location, work authorization, experience, and internship timing compatible?
5. **Evidence:** Can you demonstrate a working product, benchmark results, and clear engineering trade-offs?

Do not rely on company names alone. A smaller company with a relevant engineering problem and a realistic opening may be a better target than a more prominent company with no suitable role.

---

## Design Principles

1. **Context over collection:** Capture only what improves memory and task continuity.
2. **Local-first by default:** Keep personal data on the user's machine.
3. **Retrieval over dumping:** Return relevant memories, not entire histories.
4. **Evidence over assumptions:** Track the source of a memory and distinguish inferred state from confirmed facts.
5. **User control over automation:** Users can inspect, correct, pause, exclude, and delete.
6. **Modular architecture:** Capture, memory, retrieval, loop tracking, and MCP should be independently testable.
7. **Measurable reliability:** Evaluate changes against reproducible benchmarks.
8. **Minimal friction:** Memory should help users continue working without requiring extensive manual organization.

---

## Future Possibilities

Potential extensions, after the core system proves useful:

- Cross-project memory and related-work discovery.
- Automatic session handoffs between AI coding assistants.
- Git, GitHub, and issue-tracker integrations.
- Local semantic embeddings and hybrid retrieval.
- User-controlled memory consolidation and forgetting.
- Context-aware suggestions for resuming work.
- Team-shared memories with explicit access boundaries.
- Optional encrypted synchronization between a user's devices.
- Pluggable local and remote model providers.
- A developer-facing API for other agent applications.

These are exploratory ideas, not commitments for the first release.

---

## Contributing

DevRecall is an early-stage project focused on privacy-first personal memory, desktop context, and reliable AI-agent integration.

Potential areas for contribution include:

- macOS capture and context extraction.
- Local storage and retrieval.
- MCP tools and compatibility.
- Open-loop detection and lifecycle management.
- Evaluation datasets and benchmarking.
- Security, privacy, and performance testing.

The initial priority is to establish a working local memory pipeline, prove that retrieval is useful, and demonstrate that an AI assistant can resume work with less manual context reconstruction.

---

## License

License to be decided.

## Acknowledgements

DevRecall is inspired by the broader ecosystem of local-first AI, personal memory systems, desktop agents, MCP, and AI evaluation tooling. It is an independent project and is not affiliated with the companies listed above.
