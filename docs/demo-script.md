# Demo script (target ≤ 3 minutes)

The story every phase builds toward. Data is synthetic (Priya, Northwind, and the rest are made up), and it runs on a dedicated test Gmail account.

| Time | On screen | You say |
|---|---|---|
| 0:00–0:20 | Title card, then Minimi's inbox (or a screenshot of yours) | "Minimi finds your open loops. But you still have to close them yourself. I built the next step: an agent that closes them for you, with you approving." |
| 0:20–0:50 | Monday: Priya's email in Gmail, your "Sure, will send them over by Wednesday", then the Q3 retention sheet | "I promise something, look at the numbers, and then get pulled into other work. The app reads screen text through macOS Accessibility. No screenshots, and it's stored only on my Mac." |
| 0:50–1:10 | Wednesday: click the menu-bar icon. Open loop: *Send Priya the Q3 retention numbers · due today · evidence: your Gmail reply, Mon 10:02* | "It caught the commitment, the deadline I set myself, and the proof." |
| 1:10–2:00 | Click **Close it for me**. Live steps: finding the thread → searching memory → found Q3 retention sheet → drafting | "It finds the Gmail thread, pulls the numbers I viewed on Monday from local memory, and drafts the reply in the thread." |
| 2:00–2:25 | Draft panel with the real numbers (63.6% blended M1, up from 58.9%). Edit one word, click **Approve & Send** | "Nothing leaves without my click. That's a design choice: the model can draft, and only I can send." |
| 2:25–2:45 | Loop moves to **Closed**, with a link to the sent message | "It checks that the email is actually in Sent before closing the loop." |
| 2:45–3:00 | Architecture slide (Swift AX capture → local brain → Gemini, with the numbers from the eval report) | "Local storage, hybrid retrieval, measured loop F1, and a prompt-injection test the agent passes. Here's what I'd build next with you." |

## Must be true on demo day

- [ ] The loop is detected **once**, even though the thread was viewed twice.
- [ ] The draft contains the real numbers from the Sheets observation (Phase 3 retrieval), not `[[placeholders]]`.
- [ ] Send works only from the approval click (Phase 5).
- [ ] The whole flow runs with no terminal visible (Phase 6).
