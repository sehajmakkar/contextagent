"""Approve → send → verify, the only path that sends email (ADR-012, ADR-046).

- Approve exactly what you saw: the UI sends back the hash of the draft it displayed. If the draft changed
  since (time-of-check vs time-of-use), the approval is refused.
- Idempotent: the run is claimed with a conditional UPDATE, so a double click (or a retried request) can't
  send twice.
- Verify: after sending, read the message back and confirm Gmail labelled it SENT in the same thread before
  closing the loop. "The API returned 200" isn't the same as "it was sent".
"""

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass

from brain.db import store
from brain.loops import lifecycle
from brain.mailbox.base import Mailbox, MailboxError


class ApprovalError(Exception):
    pass


@dataclass
class SendResult:
    action_id: int
    message_id: str
    verified: bool


def draft_hash(to: list[str], subject: str, body: str) -> str:
    return hashlib.sha256(json.dumps([sorted(to), subject, body]).encode()).hexdigest()


EMAIL = re.compile(r"^[^@\s<>,;]+@[^@\s<>,;]+\.[^@\s<>,;]+$")


def approve(conn: sqlite3.Connection, mailbox: Mailbox, action_id: int, *, shown_hash: str,
            edited_body: str | None = None, edited_to: list[str] | None = None, approver: str = "user") -> SendResult:
    run = _run(conn, action_id)
    draft = json.loads(run["output_json"])["draft"]
    kind = draft.get("kind", "reply")
    if shown_hash != draft["draft_hash"]:
        raise ApprovalError("The draft changed since you saw it. Review it again before approving.")
    # Recipients: a reply's are pinned to its thread. A new email's are yours to set: you're the trusted party.
    if edited_to is not None:
        to = [addr.strip().lower() for addr in edited_to if addr.strip()]
        if kind != "new" and sorted(to) != sorted(draft["to"]):
            raise ApprovalError("A reply goes to the people in its thread; its recipients can't be changed.")
        if bad := [addr for addr in to if not EMAIL.match(addr)]:
            raise ApprovalError(f"Not a valid email address: {', '.join(bad)}")
    else:
        to = draft["to"]
    if not to:
        raise ApprovalError("Add a recipient before sending.")
    with conn:  # claim it: only one request can move awaiting_approval → sending
        claimed = conn.execute("UPDATE actions SET status = 'sending', approved_by = ?, updated_at = ? "
                               "WHERE id = ? AND status = 'awaiting_approval'", (approver, store.now(), action_id)).rowcount
    if not claimed:
        raise ApprovalError(f"Action #{action_id} is not awaiting approval (already sent, rejected or in progress).")

    try:
        body = edited_body if edited_body is not None else draft["body"]
        if body != draft["body"] or to != draft["to"]:
            mailbox.update_draft(draft["draft_id"], draft["thread_id"], to, draft["subject"], body, kind=kind)
            draft["body"], draft["to"] = body, to
        message_id = mailbox.send_draft(draft["draft_id"])
    except MailboxError as e:
        # Nothing was sent: release the claim so you can retry, and keep the error for the UI and the audit log.
        with conn:
            store.update_action(conn, action_id, status="awaiting_approval",
                                output={**json.loads(run["output_json"]), "last_error": str(e)})
        raise ApprovalError(f"Not sent: {e}. Your draft is unchanged; you can try again.") from e

    sent = mailbox.get_message(message_id)
    # A reply must land in its thread. A new email starts its own thread, so SENT is the proof.
    verified = "SENT" in sent.labels and (kind == "new" or sent.thread_id == draft["thread_id"])
    with conn:
        store.update_action(conn, action_id, status="sent" if verified else "sent_unverified",
                            output={**json.loads(run["output_json"]), "draft": draft, "sent_message_id": message_id,
                                    "sent_thread_id": sent.thread_id, "verified": verified})
        store.log_action(conn, loop_id=run["loop_id"], kind="send_email", status="sent",
                         input={"draft_id": draft["draft_id"], "approved_by": approver},
                         output={"message_id": message_id, "thread_id": sent.thread_id, "verified": verified},
                         parent_id=action_id)
        if verified:
            lifecycle.transition(conn, run["loop_id"], "closed", actor="agent",
                                 reason=f"you approved; sent message {message_id}, confirmed in Sent")
    return SendResult(action_id, message_id, verified)


def reject(conn: sqlite3.Connection, mailbox: Mailbox, action_id: int, reason: str = "rejected") -> None:
    run = _run(conn, action_id)
    with conn:
        claimed = conn.execute("UPDATE actions SET status = 'rejected', updated_at = ? "
                               "WHERE id = ? AND status = 'awaiting_approval'", (store.now(), action_id)).rowcount
        if not claimed:
            raise ApprovalError(f"Action #{action_id} is not awaiting approval.")
        lifecycle.transition(conn, run["loop_id"], "open", actor="user", reason=f"draft rejected: {reason}")
    mailbox.delete_draft(json.loads(run["output_json"])["draft"]["draft_id"])


def _run(conn: sqlite3.Connection, action_id: int) -> sqlite3.Row:
    run = conn.execute("SELECT * FROM actions WHERE id = ? AND kind = 'agent_run'", (action_id,)).fetchone()
    if run is None:
        raise ApprovalError(f"No agent run #{action_id}")
    return run
