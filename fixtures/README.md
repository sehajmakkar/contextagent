# Fixtures

Synthetic data only. Every person, email, and company here is made up (`*.example` domains). That makes it safe for the Gemini free tier (ADR-014).

`sessions/*.jsonl`: one **observation** per line, in the same shape the Swift app will `POST /observations` in Phase 2 (`captured_at`, `app_name`, `bundle_id`, `window_title`, `url`, `text`). The text is written to look like Accessibility-tree output: flattened, with UI labels like "Reply" and "Inbox 12" mixed in.

## `demo_week.jsonl`: expected loops (the answer key for evals later)

| # | Observation | Expected |
|---|---|---|
| 1 | Gmail: Priya asks for Q3 retention numbers, you reply "by Wednesday" | **I owe** Priya: Q3 retention numbers, due 2026-10-21 (**the demo loop**) |
| 2 | Sheets: Q3 retention cohort table | none (this is the *memory* the agent needs in Phase 3) |
| 3 | Slack: Rahul asks for PR #482 review, you say "after lunch" | **I owe** Rahul: review of PR #482, due 2026-10-19 |
| 4 | Terminal: a failing test | none |
| 5 | Slack: you reviewed #482 and Rahul merged it | none (it **closes** loop #3, which is Phase 4 closure detection) |
| 6 | Gmail: recruiter Maya asks for your availability | **I owe** Maya: a reply with times for next week |
| 7 | Slack DM: Ananya will send design specs by Friday, plus "grab coffee sometime" | **They owe** me: design specs, due 2026-10-23. The coffee line is *not* a loop (too vague) |
| 8 | Notes: launch sync action items | **I owe**: launch blog draft, due 2026-10-28. Dev's and Priya's items are theirs, not owed to me (tricky) |
| 9 | Gmail promo: "Don't forget, renews Nov 1" | none (marketing, tricky) |
| 10 | Gmail: Jordan asks for the NDA, you already sent it | none (already closed in the same view) |
| 11 | Article | none |
| 12 | VS Code: a `TODO` comment | none (a code TODO isn't a commitment to a person) |
| 13 | Calendar: Q3 review on Thursday | none (context that explains why loop #1 matters) |
| 14 | Gmail: landlord asks you to confirm the lease renewal by Oct 31 | **I owe** Karan: lease renewal answer, due 2026-10-31 |
| 15 | Gmail: you revisit the Priya thread (same text, different inbox count) | **no new loop.** It should attach to loop #1 (a dedupe test) |
