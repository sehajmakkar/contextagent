"""Gmail through the official API (ADR-044). OAuth installed-app flow; the token lives in the macOS Keychain.

Scopes: gmail.readonly (read threads) + gmail.compose (drafts). gmail.compose *also* allows sending: Google
has no "drafts but not send" scope. So "the model can never send" is enforced by our architecture
(send isn't a model tool; only the approval endpoint calls send_draft), not by OAuth (ADR-045).
"""

import base64
import json
from email.message import EmailMessage
from pathlib import Path

import keyring
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from brain.mailbox.base import Draft, MailboxError, MailMessage, ThreadSummary, addresses

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly", "https://www.googleapis.com/auth/gmail.compose"]
KEYCHAIN_SERVICE = "ContextAgent"
KEYCHAIN_ACCOUNT = "gmail-oauth-token"
MAX_BODY_CHARS = 4_000


def login(client_secrets: Path) -> str:
    """Open the browser consent screen once, then keep the refresh token in the Keychain. Returns the account."""
    if not client_secrets.exists():
        raise MailboxError(f"OAuth client file not found: {client_secrets} (see plan.md, Phase 5 setup)")
    creds = InstalledAppFlow.from_client_secrets_file(str(client_secrets), SCOPES).run_local_server(port=0)
    keyring.set_password(KEYCHAIN_SERVICE, KEYCHAIN_ACCOUNT, creds.to_json())
    return GmailMailbox.connect().account


def logout() -> None:
    try:
        keyring.delete_password(KEYCHAIN_SERVICE, KEYCHAIN_ACCOUNT)
    except keyring.errors.PasswordDeleteError:
        pass


class GmailMailbox:
    def __init__(self, service, account: str) -> None:
        self._s = service.users()
        self.account = account.lower()

    @classmethod
    def connect(cls) -> "GmailMailbox":
        stored = keyring.get_password(KEYCHAIN_SERVICE, KEYCHAIN_ACCOUNT)
        if not stored:
            raise MailboxError("Not connected to Gmail. Run `brain gmail-login` first.")
        creds = Credentials.from_authorized_user_info(json.loads(stored), SCOPES)
        if not creds.valid and creds.refresh_token:
            creds.refresh(Request())  # access tokens last ~1h; the refresh token gets a new one
            keyring.set_password(KEYCHAIN_SERVICE, KEYCHAIN_ACCOUNT, creds.to_json())
        service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        account = service.users().getProfile(userId="me").execute()["emailAddress"]
        return cls(service, account)

    def search_threads(self, query: str, max_results: int = 5) -> list[ThreadSummary]:
        found = self._call(self._s.threads().list(userId="me", q=query, maxResults=max_results))
        out = []
        for t in found.get("threads", []):
            thread = self._call(self._s.threads().get(userId="me", id=t["id"], format="metadata",
                                                      metadataHeaders=["From", "To", "Cc", "Subject", "Date"]))
            messages = thread.get("messages", [])
            people = set()
            for m in messages:
                h = _headers(m)
                people.update(addresses(h.get("from", "")) + addresses(h.get("to", "")) + addresses(h.get("cc", "")))
            last = _headers(messages[-1]) if messages else {}
            out.append(ThreadSummary(thread_id=t["id"], subject=_headers(messages[0]).get("subject", "") if messages else "",
                                     participants=sorted(people), snippet=messages[-1].get("snippet", "") if messages else "",
                                     last_date=last.get("date", "")))
        return out

    def get_thread(self, thread_id: str) -> list[MailMessage]:
        thread = self._call(self._s.threads().get(userId="me", id=thread_id, format="full"))
        return [_message(m) for m in thread.get("messages", [])]

    def create_draft(self, thread_id: str, to: list[str], subject: str, body: str) -> Draft:
        created = self._call(self._s.drafts().create(userId="me", body=self._draft_body(thread_id, to, subject, body)))
        return Draft(id=created["id"], thread_id=thread_id, to=to, subject=subject, body=body)

    def create_new_draft(self, to: list[str], subject: str, body: str) -> Draft:
        """A fresh email, not a reply: no threadId, no In-Reply-To. Gmail starts a new thread for it."""
        created = self._call(self._s.drafts().create(userId="me", body=self._draft_body(None, to, subject, body)))
        return Draft(id=created["id"], thread_id=created["message"].get("threadId"), to=to, subject=subject,
                     body=body, kind="new")

    def update_draft(self, draft_id: str, thread_id: str | None, to: list[str], subject: str, body: str,
                     kind: str = "reply") -> Draft:
        reply_to = thread_id if kind == "reply" else None
        self._call(self._s.drafts().update(userId="me", id=draft_id,
                                           body={"id": draft_id, **self._draft_body(reply_to, to, subject, body)}))
        return Draft(id=draft_id, thread_id=thread_id, to=to, subject=subject, body=body, kind=kind)

    def get_draft(self, draft_id: str) -> Draft:
        d = self._call(self._s.drafts().get(userId="me", id=draft_id, format="full"))
        m = _message(d["message"])
        return Draft(id=draft_id, thread_id=m.thread_id, to=m.to, subject=m.subject, body=m.body)

    def delete_draft(self, draft_id: str) -> None:
        try:
            self._call(self._s.drafts().delete(userId="me", id=draft_id))
        except MailboxError:
            pass  # already gone (sent or deleted by hand)

    def send_draft(self, draft_id: str) -> str:
        return self._call(self._s.drafts().send(userId="me", body={"id": draft_id}))["id"]

    def get_message(self, message_id: str) -> MailMessage:
        return _message(self._call(self._s.messages().get(userId="me", id=message_id, format="full")))

    def _draft_body(self, thread_id: str | None, to: list[str], subject: str, body: str) -> dict:
        msg = EmailMessage()
        if to:  # a new email may wait for you to add the recipient
            msg["To"] = ", ".join(to)
        msg["Subject"] = subject
        if thread_id:
            last = self.get_thread(thread_id)[-1]
            if last.message_id_header:  # these headers make it a reply in the same conversation everywhere
                msg["In-Reply-To"] = last.message_id_header
                msg["References"] = last.message_id_header
        msg.set_content(body)
        message = {"raw": base64.urlsafe_b64encode(msg.as_bytes()).decode()}
        if thread_id:
            message["threadId"] = thread_id
        return {"message": message}

    @staticmethod
    def _call(request):
        try:
            return request.execute()
        except HttpError as e:
            raise MailboxError(f"Gmail API error {e.status_code}: {e.reason}") from e


def _headers(message: dict) -> dict[str, str]:
    return {h["name"].lower(): h["value"] for h in message.get("payload", {}).get("headers", [])}


def _message(m: dict) -> MailMessage:
    h = _headers(m)
    return MailMessage(id=m["id"], thread_id=m["threadId"], sender=h.get("from", ""), to=addresses(h.get("to", "")),
                       cc=addresses(h.get("cc", "")), date=h.get("date", ""), subject=h.get("subject", ""),
                       body=_plain_text(m.get("payload", {}))[:MAX_BODY_CHARS],
                       message_id_header=h.get("message-id", ""), labels=m.get("labelIds", []))


def _plain_text(payload: dict) -> str:
    """The text/plain part of a (possibly multipart) message."""
    if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")
    for part in payload.get("parts", []) or []:
        if text := _plain_text(part):
            return text
    return ""


def open_mailbox(settings) -> "GmailMailbox":
    """The mailbox the agent uses: your connected Gmail."""
    return GmailMailbox.connect()
