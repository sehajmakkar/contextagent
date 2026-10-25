"""An in-memory mailbox for tests and agent evals (and the Phase 7 demo mode). Deterministic, no network."""

import itertools
from dataclasses import replace

from brain.mailbox.base import Draft, MailboxError, MailMessage, ThreadSummary, addresses


class FakeMailbox:
    def __init__(self, account: str, threads: dict[str, list[MailMessage]]) -> None:
        self.account = account.lower()
        self.threads = threads
        self.drafts: dict[str, Draft] = {}
        self.sent: list[MailMessage] = []
        self._ids = itertools.count(1)

    @classmethod
    def from_spec(cls, account: str, spec: list[dict]) -> "FakeMailbox":
        """spec: [{"thread_id", "subject", "messages": [{"from", "to", "cc"?, "date", "body"}]}]"""
        threads = {}
        for t in spec:
            threads[t["thread_id"]] = [
                MailMessage(id=f"{t['thread_id']}-m{i}", thread_id=t["thread_id"], sender=m["from"],
                            to=addresses(m.get("to", "")), cc=addresses(m.get("cc", "")), date=m["date"],
                            subject=t["subject"], body=m["body"], message_id_header=f"<{t['thread_id']}-m{i}@fake>")
                for i, m in enumerate(t["messages"], start=1)
            ]
        return cls(account, threads)

    def search_threads(self, query: str, max_results: int = 5) -> list[ThreadSummary]:
        words = [w.lower() for w in query.split() if len(w) > 2 and ":" not in w]
        scored = []
        for thread_id, messages in self.threads.items():
            haystack = " ".join(f"{m.subject} {m.sender} {' '.join(m.to)} {m.body}" for m in messages).lower()
            score = sum(w in haystack for w in words)
            if score:
                scored.append((score, thread_id, messages))
        scored.sort(key=lambda s: -s[0])
        return [ThreadSummary(thread_id=t, subject=ms[0].subject,
                              participants=sorted(set().union(*(m.participants for m in ms))),
                              snippet=ms[-1].body[:120], last_date=ms[-1].date)
                for _, t, ms in scored[:max_results]]

    def get_thread(self, thread_id: str) -> list[MailMessage]:
        if thread_id not in self.threads:
            raise MailboxError(f"no thread {thread_id}")
        return self.threads[thread_id]

    def create_draft(self, thread_id: str, to: list[str], subject: str, body: str) -> Draft:
        self.get_thread(thread_id)
        draft = Draft(id=f"d{next(self._ids)}", thread_id=thread_id, to=to, subject=subject, body=body)
        self.drafts[draft.id] = draft
        return draft

    def update_draft(self, draft_id: str, thread_id: str, to: list[str], subject: str, body: str) -> Draft:
        draft = replace(self.get_draft(draft_id), thread_id=thread_id, to=to, subject=subject, body=body)
        self.drafts[draft_id] = draft
        return draft

    def get_draft(self, draft_id: str) -> Draft:
        if draft_id not in self.drafts:
            raise MailboxError(f"no draft {draft_id}")
        return self.drafts[draft_id]

    def delete_draft(self, draft_id: str) -> None:
        self.drafts.pop(draft_id, None)

    def send_draft(self, draft_id: str) -> str:
        draft = self.drafts.pop(draft_id, None)
        if draft is None:
            raise MailboxError(f"no draft {draft_id}")
        message = MailMessage(id=f"sent-{next(self._ids)}", thread_id=draft.thread_id, sender=self.account,
                              to=draft.to, cc=[], date="now", subject=draft.subject, body=draft.body, labels=["SENT"])
        self.threads[draft.thread_id].append(message)
        self.sent.append(message)
        return message.id

    def get_message(self, message_id: str) -> MailMessage:
        for messages in self.threads.values():
            for m in messages:
                if m.id == message_id:
                    return m
        raise MailboxError(f"no message {message_id}")
