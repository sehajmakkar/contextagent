"""Least privilege at the query level: the agent only sees threads matching a fixed Gmail filter (ADR-048).

OAuth scopes are all-or-nothing per mailbox (gmail.readonly reads everything). On the free tier, whatever the
agent reads goes to a provider that may use it (ADR-014), so on a real inbox we narrow what it can see:
every search gets the scope appended, and only threads a scoped search returned can be opened or replied in.
"""

from brain.mailbox.base import Draft, Mailbox, MailboxError, MailMessage, ThreadSummary


class ScopedMailbox:
    def __init__(self, inner: Mailbox, scope: str) -> None:
        self._inner = inner
        self.scope = scope
        self.account = inner.account
        self._visible: set[str] = set()

    def search_threads(self, query: str, max_results: int = 5) -> list[ThreadSummary]:
        found = self._inner.search_threads(f"({query}) {self.scope}", max_results)
        self._visible.update(t.thread_id for t in found)
        return found

    def get_thread(self, thread_id: str) -> list[MailMessage]:
        return self._inner.get_thread(self._check(thread_id))

    def create_draft(self, thread_id: str, to: list[str], subject: str, body: str) -> Draft:
        return self._inner.create_draft(self._check(thread_id), to, subject, body)

    def update_draft(self, draft_id: str, thread_id: str, to: list[str], subject: str, body: str) -> Draft:
        return self._inner.update_draft(draft_id, self._check(thread_id), to, subject, body)

    # Approval-side calls work on drafts this run created, so they pass straight through.
    def get_draft(self, draft_id: str) -> Draft:
        return self._inner.get_draft(draft_id)

    def delete_draft(self, draft_id: str) -> None:
        self._inner.delete_draft(draft_id)

    def send_draft(self, draft_id: str) -> str:
        return self._inner.send_draft(draft_id)

    def get_message(self, message_id: str) -> MailMessage:
        return self._inner.get_message(message_id)

    def _check(self, thread_id: str) -> str:
        if thread_id not in self._visible:
            raise MailboxError(f"Thread {thread_id} is outside the allowed mailbox scope ({self.scope}).")
        return thread_id
