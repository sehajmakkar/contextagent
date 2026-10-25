# macOS Context Agent

### Remember your work. Help you get it done.

A privacy-first AI assistant for macOS that understands your desktop context, remembers important information, tracks unfinished tasks, and helps complete them through connected tools. Unlike traditional memory tools, it aims to move beyond identifying what needs to be done and help users actually do it.

## Features

- **Context Capture:** Extract useful context from user-approved screen capture.
- **Automatic Open-Loop Tracking:** Identify tasks, commitments, follow-ups, and completed work.
- **Persistent Memory:** Remember relevant context across applications and work sessions.
- **AI Action Agent:** Resolve selected tasks through connected services, starting with email workflows etc.
- **MCP Integration (v2):** Let compatible AI assistants access relevant memories and context.
- **Privacy First:** Store data locally on the Mac by default, with user-controlled permissions and deletion.

## How it works

```mermaid
flowchart TD
    subgraph APP["Swift menu-bar app (native)"]
        AX["Accessibility events<br/>focus, window, value changed"] --> CO["Coalescer<br/>debounce + max wait, flush on leave"]
        CO --> RD["Read the focused window's text<br/>no screenshots, password fields and denylisted apps skipped"]
        INBOX["Inbox UI<br/>open loops, Close it for me"]
        REVIEW["Draft review<br/>edit, fill placeholders, Approve & Send or Reject"]
    end

    subgraph BRAIN["Python brain (FastAPI on 127.0.0.1)"]
        ING["Ingest<br/>redact secrets, drop duplicates, keep new lines"] --> DB[("SQLite on your Mac<br/>FTS5 + sqlite-vec")]
        DB --> EP["Episodes<br/>one visit to one window, closed when you leave"]
        EP --> MEM["Memory extraction<br/>facts with a quote that proves them"]
        MEM --> EMB["Embeddings<br/>hybrid search: keywords + vectors"]
        EP --> LOOPS["Loop detection<br/>promises, asks, follow-ups"]
        LOOPS --> DEDUPE["Dedupe + lifecycle<br/>same loop seen twice, verified closes"]
        AGENT["Agent loop (Gemini function calling)<br/>search memory, find and read the thread"]
        AGENT --> GUARD{"Guardrails in code<br/>recipients in thread or known contact,<br/>no decisions on your behalf"}
        GUARD --> DRAFT["Gmail draft<br/>reply in thread, or a new email"]
        SEND["Approval endpoint<br/>same draft you saw, claimed once"] --> VERIFY["Verify it's in Sent<br/>loop closed with proof"]
    end

    RD -- "POST /observations" --> ING
    DEDUPE --> INBOX
    INBOX -- "Close it for me" --> AGENT
    DRAFT -- "live steps (SSE)" --> REVIEW
    REVIEW -- "Approve & Send (your click)" --> SEND
    EMB -. "facts for the reply" .-> AGENT

    MEM <-.-> GEM(["Gemini API<br/>stateless calls, nothing stored"])
    LOOPS <-.-> GEM
    AGENT <-.-> GEM
    DRAFT <-.-> GMAIL(["Gmail API<br/>OAuth token in the macOS Keychain"])
    SEND <-.-> GMAIL
```

- **Nothing is sent without your click.** The agent has no send tool; only the approval endpoint sends, and only the exact draft you reviewed.
- **Screen text is data, not instructions.** It's delimited in every prompt, and the recipient and authority rules are enforced in code, not left to the model.
- **One file holds everything:** `~/Library/Application Support/ContextAgent/brain.db`. Pause capture any time; delete everything from Settings.

### Inspired by Minimi (projectminimi.com)
- adding the ai action agent feature i.e. ai agent can close the open loops for you.

## Goal

Build a local-first memory and action layer that helps AI assistants understand your work and safely take action on your behalf.

## Status

In development.  
  
## Target Companies

projectminimi.com, heyclicky.com
others: Screenpipe, Sentient OS, Pickle, Nessie, IrisGo, jo, Egoist Machines, Crater, Town, Granola, Memory Store, Epicenter, Almanac, Supermemory, Mem0.