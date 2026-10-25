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


def approve(conn: sqlite3.Connection, mailbox: Mailbox, action_id: int, *, shown_hash: str,
            edited_body: str | None = None, approver: str = "user") -> SendResult:
    run = _run(conn, action_id)
    draft = json.loads(run["output_json"])["draft"]
    if shown_hash != draft["draft_hash"]:
        raise ApprovalError("The draft changed since you saw it. Review it again before approving.")
    with conn:  # claim it: only one request can move awaiting_approval → sending
        claimed = conn.execute("UPDATE actions SET status = 'sending', approved_by = ?, updated_at = ? "
                               "WHERE id = ? AND status = 'awaiting_approval'", (approver, store.now(), action_id)).rowcount
    if not claimed:
        raise ApprovalError(f"Action #{action_id} is not awaiting approval (already sent, rejected or in progress).")

    try:
        if edited_body is not None and edited_body != draft["body"]:
            mailbox.update_draft(draft["draft_id"], draft["thread_id"], draft["to"], draft["subject"], edited_body)
            draft["body"] = edited_body
        message_id = mailbox.send_draft(draft["draft_id"])
    except MailboxError as e:
        with conn:
            store.update_action(conn, action_id, status="failed", output={**json.loads(run["output_json"]), "error": str(e)})
            lifecycle.transition(conn, run["loop_id"], "open", actor="agent", reason=f"send failed: {e}")
        raise ApprovalError(f"Sending failed: {e}") from e

    sent = mailbox.get_message(message_id)
    verified = "SENT" in sent.labels and sent.thread_id == draft["thread_id"]
    with conn:
        store.update_action(conn, action_id, status="sent" if verified else "sent_unverified",
                            output={**json.loads(run["output_json"]), "draft": draft, "sent_message_id": message_id,
                                    "verified": verified})
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
