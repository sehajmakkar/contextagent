# McCuck
### A privacy-first memory layer for macOS and AI agents

DevRecall is a local-first context engine that helps developers and AI assistants remember what matters across desktop apps and work sessions. It captures useful context, tracks open loops, and makes relevant memories accessible through MCP.

**Your AI assistant should remember your work, not just your latest prompt.**

## Core Features

- **Desktop Context Capture:** Capture useful context across desktop workflows, with optional screen capture and user-controlled recording.
- **Automatic Open-Loop Tracking:** Identify unfinished tasks, commitments, follow-ups, and completed work.
- **Persistent Memory:** Remember project context, decisions, preferences, previous work, and recurring patterns across sessions.
- **MCP Integration:** Let compatible AI assistants, including Claude and GPT-based clients, retrieve relevant context through tools.
- **Smart Retrieval:** Search memories using keywords, semantic similarity, recency, and project context.
- **Session Resumption:** Generate concise summaries of previous work, unresolved issues, and suggested next actions.
- **Privacy-First by Design:** Store personal context locally on macOS by default, with transparent permissions, app exclusions, redaction, and user-controlled deletion.

## How It Works

1. **Capture:** Collect user-approved context from desktop activity and explicit inputs.
2. **Process:** Extract useful information, identify tasks and decisions, and detect open or closed loops.
3. **Store:** Organize memories locally with timestamps, sources, projects, and searchable metadata.
4. **Retrieve:** Rank relevant memories for a question or task.
5. **Connect:** Expose memory and context tools to AI assistants through MCP.

## Initial Tech Stack

- **macOS App:** Swift / SwiftUI
- **Local Storage:** SQLite + FTS5
- **Memory & MCP Server:** TypeScript
- **Retrieval:** Full-text search first; embeddings and hybrid retrieval later
- **Context Processing:** Background jobs, structured extraction, and optional AI models

## Evaluation Metrics

- **Retrieval Quality:** Recall@5, Precision@5, and overall retrieval precision/recall.
- **Latency:** p50 and p95 retrieval latency.
- **Context Efficiency:** Tokens supplied versus full-history context; estimated tokens saved.
- **Memory Accuracy:** Correctness of extracted facts, task states, and open/closed-loop detection.
- **Task Resumption:** Whether an assistant can correctly identify prior work and the next action.
- **Answer Quality:** Accuracy and relevance of responses with retrieved context.
- **Resource Usage:** CPU, memory, battery impact, and local storage growth.
- **Privacy & Safety:** Redaction effectiveness, permission enforcement, app exclusions, and deletion correctness.

## Potential Target Companies

Companies to study, learn from, or approach for relevant engineering opportunities. This list does **not** imply they are currently hiring or that every role is suitable.

**Desktop memory & personal AI:** Minimi, HeyClicky, Screenpipe, Sentient OS, Pickle, Nessie, IrisGo, jo, Egoist Machines, Crater, Town, Granola, Memory Store, Epicenter, Almanac, Supermemory, Mem0.

**AI agents, infrastructure & reliability:** Ressl AI, Agnost AI, Maxim AI, Cekura, BentoLabs, DrDroid, CodeAnt AI, TestMu AI, Raga AI, Composio, TrueFoundry, Portkey, Metorial, Dexto, Scalekit, UnifyApps, Lyzr.

**AI media & workflow products:** Cardboard, Clueso, Trupeer, InVideo, Spyne.ai.

## Guiding Principles

- Local-first storage and privacy by default.
- Capture useful context, not everything indiscriminately.
- Retrieve relevant memories instead of dumping entire histories.
- Give users control over what is captured and remembered.
- Measure retrieval quality and task usefulness, not just feature count.

## Project Status

Early-stage project. Initial focus: a working macOS context store, open-loop tracking, MCP tools, and a reproducible evaluation suite.
