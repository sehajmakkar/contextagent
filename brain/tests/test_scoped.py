import pytest

from brain.config import Settings
from brain.mailbox.base import MailboxError
from brain.mailbox.fake import FakeMailbox
from brain.mailbox.gmail import open_mailbox
from brain.mailbox.scoped import ScopedMailbox

ME = "me@example.com"
SPEC = [{"thread_id": "test", "subject": "[CA-TEST] Q3", "messages": [{"from": "a@x.example", "to": ME, "date": "d", "body": "quarterly numbers"}]},
        {"thread_id": "private", "subject": "Bank statement", "messages": [{"from": "bank@x.example", "to": ME, "date": "d", "body": "quarterly balance"}]}]


class Spy(FakeMailbox):
    def search_threads(self, query, max_results=5):
        self.last_query = query
        bare = query.replace('subject:"[CA-TEST]"', "").replace("(", " ").replace(")", " ")
        return [t for t in super().search_threads(bare, max_results)
                if "[CA-TEST]" in t.subject]  # what Gmail would do with the filter


def test_every_search_carries_the_scope_and_only_found_threads_open():
    box = ScopedMailbox(Spy.from_spec(ME, SPEC), 'subject:"[CA-TEST]"')
    [t] = box.search_threads("quarterly")
    assert box._inner.last_query == '(quarterly) subject:"[CA-TEST]"' and t.thread_id == "test"
    assert box.get_thread("test")
    with pytest.raises(MailboxError, match="outside the allowed mailbox scope"):
        box.get_thread("private")  # a thread id the agent guessed or was told by injected text
    with pytest.raises(MailboxError):
        box.create_draft("private", ["bank@x.example"], "Re", "hi")


def test_free_tier_refuses_an_unscoped_real_mailbox():
    with pytest.raises(MailboxError, match="Set MAIL_SCOPE"):
        open_mailbox(Settings(gemini_tier="free", mail_scope=""))
