# Minimi teardown

Sources: Minimi's public site (read 2026-10-24) and your own use of the app, including screenshots of the dashboard and compact panel (2026-10-25). _Add your own observations here. This doc is your outreach hook._

## What it is

- A macOS menu-bar app (the cat icon). It reads screen content "via Apple's accessibility infrastructure" with no screenshots, keeps memories as embeddings in a local vector DB, and sends inference to Gemini, OpenAI and Deepgram through its backend (on a paid plan).
- Two products: **Memory MCP** (plug your memories into Claude, ChatGPT and others) and the **Open loops Inbox**.

## UI, from your screenshots

**Dashboard window**
- **Your Inbox:** "0 open loops · 0 closed", a greeting ("Good evening, Sehaj 👋 / Your slate is completely clean"), Dismiss, and an empty state ("You're all set!"). The note button at the bottom right adds a loop by hand.
- **Recent memories:** a list of one-line memories, each with its source app's icon (all Chrome in your session).
- **Discover minimi:** onboarding checklist ("Double-tap Control to open Inbox", "Connect minimi with your LLM").

**Compact panel:** the same inbox in a small pinnable window. Open loops appear with a **Resolve** button that turns them into closed loops.

**Open-loop cards** (third screenshot): a filter row (All / Google Chrome / WhatsApp). Each card has the source app icon, window or chat ("You (self-message)"), a title ("Email resume to … for Strelema role"), a one-line *why* ("no deadline is listed"), and the **source quote**. **Self-messages count as loops.**

## Observations (where we differ)

1. **Memory quality.** Several "memories" in your screenshot are UI state, not knowledge: *"You are logged into LinkedIn as Sehaj Preet"*, *"You have 2 Network and 8 other new notifications"*, *"You are currently active on LinkedIn."* Our extractor explicitly rejects app chrome, notifications and generic content, and requires standalone sentences with names, figures and dates (ADR-034). Some memories are also vague (*"MAIT achieved multiple top rankings"*, *"You and Kunwar Anmol Singh discussed an interview"*: which interview, and when?).
2. **Resolving vs closing.** Minimi's **Resolve** marks a loop done. **Our pitch: "Close it for me."** The agent drafts the reply in the right thread from your memories, you approve it, it sends, and then it verifies (ADR-001, ADR-012).
3. **Measurable quality.** We can show numbers: loop precision and recall on a labelled set, retrieval Recall@1 by mode, and a capture funnel (−55% chars before any LLM call).
4. **Privacy on the free tier.** We hold real captures back from free-tier inference (ADR-027). Minimi relies on a paid plan's terms.

## Ideas to borrow for Phase 6

- Loop cards with an app filter row, source quote and a "why still open" line. Our API already returns `source_app`, `window_title`, `quote` and `note` per loop.
- The two-pane dashboard (Inbox + Recent memories) and the compact pinned panel.
- The app icon next to each memory (provenance at a glance).
- A greeting with an empty state that reassures ("You're all set").
- A global shortcut (double-tap Control) to open the inbox.
