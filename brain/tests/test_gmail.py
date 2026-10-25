"""GmailMailbox against canned API responses: MIME parsing and reply threading, without a network."""

import base64
import email
import email.policy
from unittest.mock import MagicMock

from brain.mailbox.gmail import GmailMailbox


def b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode()


THREAD = {"id": "t1", "messages": [{
    "id": "m1", "threadId": "t1", "labelIds": ["INBOX"],
    "payload": {"mimeType": "multipart/alternative", "headers": [
        {"name": "From", "value": "Priya Sharma <priya.sharma@northwind.example>"},
        {"name": "To", "value": "Sehaj <sehaj.demo@example.com>"},
        {"name": "Subject", "value": "Q3 retention numbers"},
        {"name": "Message-ID", "value": "<CAF123@mail.gmail.com>"}],
        "parts": [{"mimeType": "text/html", "body": {"data": b64("<p>html version</p>")}},
                  {"mimeType": "text/plain", "body": {"data": b64("Can you send the Q3 numbers?")}}]}}]}


def mailbox() -> tuple[GmailMailbox, MagicMock]:
    service = MagicMock()
    users = service.users.return_value
    users.threads.return_value.get.return_value.execute.return_value = THREAD
    users.drafts.return_value.create.return_value.execute.return_value = {"id": "d1"}
    return GmailMailbox(service, "sehaj.demo@example.com"), users


def test_thread_parsing_prefers_plain_text_and_keeps_participants():
    box, _ = mailbox()
    [m] = box.get_thread("t1")
    assert m.body == "Can you send the Q3 numbers?"
    assert m.participants == {"priya.sharma@northwind.example", "sehaj.demo@example.com"}
    assert m.message_id_header == "<CAF123@mail.gmail.com>"


def test_drafts_are_real_replies_in_the_same_thread():
    box, users = mailbox()
    box.create_draft("t1", ["priya.sharma@northwind.example"], "Re: Q3 retention numbers", "Hi Priya, 63.6%.")
    body = users.drafts.return_value.create.call_args.kwargs["body"]["message"]
    assert body["threadId"] == "t1"
    sent = email.message_from_bytes(base64.urlsafe_b64decode(body["raw"]), policy=email.policy.default)
    # Without these two headers the reply shows up as a brand-new email in Priya's inbox.
    assert sent["In-Reply-To"] == "<CAF123@mail.gmail.com>" and sent["References"] == "<CAF123@mail.gmail.com>"
    assert sent["To"] == "priya.sharma@northwind.example" and "63.6%" in sent.get_content()
