"""The mailbox interface the agent works through. Gmail is one implementation; a fake one backs tests and evals."""

from dataclasses import dataclass, field
from email.utils import getaddresses
from typing import Protocol


@dataclass(frozen=True)
class MailMessage:
    id: str
    thread_id: str
    sender: str
    to: list[str]
    cc: list[str]
    date: str
    subject: str
    body: str
    message_id_header: str = ""          # RFC 5322 Message-ID, for In-Reply-To / References
    labels: list[str] = field(default_factory=list)

    @property
    def participants(self) -> set[str]:
        return {a for a in [*addresses(self.sender), *self.to, *self.cc] if a}


@dataclass(frozen=True)
class ThreadSummary:
    thread_id: str
    subject: str
    participants: list[str]
    snippet: str
    last_date: str


@dataclass(frozen=True)
class Draft:
    id: str
    thread_id: str
    to: list[str]
    subject: str
    body: str


class MailboxError(RuntimeError):
    pass


class Mailbox(Protocol):
    account: str  # the user's own address

    def search_threads(self, query: str, max_results: int = 5) -> list[ThreadSummary]: ...
    def get_thread(self, thread_id: str) -> list[MailMessage]: ...
    def create_draft(self, thread_id: str, to: list[str], subject: str, body: str) -> Draft: ...
    def update_draft(self, draft_id: str, thread_id: str, to: list[str], subject: str, body: str) -> Draft: ...
    def get_draft(self, draft_id: str) -> Draft: ...
    def delete_draft(self, draft_id: str) -> None: ...
    def send_draft(self, draft_id: str) -> str: ...          # returns the sent message id
    def get_message(self, message_id: str) -> MailMessage: ...


def addresses(header: str) -> list[str]:
    """'Priya Sharma <priya@x.com>, b@y.com' → ['priya@x.com', 'b@y.com'] (lower-case)."""
    return [addr.lower() for _, addr in getaddresses([header or ""]) if addr]
