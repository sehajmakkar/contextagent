"""The agent's tools: typed, risk-classed, and guarded in code (ADR-026, ADR-045).

Risk classes: read (no side effects) · draft (reversible, private) · execute (outward, irreversible).
There is deliberately no execute tool: sending happens only through the approval endpoint (ADR-012).
Guardrails live here, in code, because a prompt can be talked out of a rule and a check can't.
"""

import sqlite3
from dataclasses import dataclass, field
from typing import Callable, Literal

from pydantic import BaseModel, Field, ValidationError

from brain.config import Settings
from brain.llm.client import LLMClient, ToolCall, ToolSpec
from brain.mailbox.base import Mailbox, MailboxError
from brain.memory import retrieve

Risk = Literal["read", "draft", "execute"]
MAX_BODY_CHARS = 3_000


class ToolError(Exception):
    """A refusal or failure reported back to the model as {"error": ...}, so it can correct itself."""


@dataclass
class Context:
    conn: sqlite3.Connection
    llm: LLMClient
    settings: Settings
    mailbox: Mailbox
    loop: sqlite3.Row
    participants: dict[str, set[str]] = field(default_factory=dict)  # thread id → addresses seen in it
    draft: object | None = None
    finished: dict | None = None


# --- argument models (validated before any tool runs) -----------------------

class SearchMemoryArgs(BaseModel):
    query: str = Field(description="What to look for, e.g. 'Q3 retention numbers'.")
    k: int = Field(default=5, ge=1, le=10)


class MailSearchArgs(BaseModel):
    query: str = Field(description="Gmail search, e.g. 'from:priya Q3 retention' or a subject.")
    max_results: int = Field(default=5, ge=1, le=10)


class GetThreadArgs(BaseModel):
    thread_id: str


class DraftArgs(BaseModel):
    thread_id: str = Field(description="The thread to reply in (from mail_search).")
    to: list[str] = Field(description="Recipient addresses. Only people already in the thread.")
    subject: str = Field(description="Usually 'Re: <original subject>'.")
    body: str = Field(description="Plain-text reply, signed as the user. Use [[placeholders]] for anything missing.")


class FinishArgs(BaseModel):
    outcome: Literal["drafted", "already_done", "cannot_close"]
    summary: str = Field(description="One or two sentences for the user: what you did and why.")
    missing_info: list[str] = Field(default_factory=list, description="Facts or files the user must add before sending.")


# --- handlers -------------------------------------------------------------------

def search_memory(ctx: Context, a: SearchMemoryArgs) -> dict:
    hits = retrieve.search(ctx.conn, ctx.llm, ctx.settings, a.query, k=a.k, mode="hybrid")
    return {"memories": [{"untrusted_text": h.text, "kind": h.kind, "when": h.happened_at[:16], "app": h.app_name}
                         for h in hits]}


def mail_search(ctx: Context, a: MailSearchArgs) -> dict:
    return {"threads": [{"thread_id": t.thread_id, "subject": t.subject, "participants": t.participants,
                         "last_date": t.last_date, "untrusted_snippet": t.snippet}
                        for t in ctx.mailbox.search_threads(a.query, a.max_results)]}


def mail_get_thread(ctx: Context, a: GetThreadArgs) -> dict:
    messages = ctx.mailbox.get_thread(a.thread_id)
    ctx.participants[a.thread_id] = set().union(*(m.participants for m in messages)) if messages else set()
    return {"thread_id": a.thread_id, "messages": [
        {"from": m.sender, "to": m.to, "cc": m.cc, "date": m.date, "subject": m.subject,
         "untrusted_body": m.body[:MAX_BODY_CHARS]} for m in messages]}


def create_draft(ctx: Context, a: DraftArgs) -> dict:
    if a.thread_id not in ctx.participants:
        raise ToolError("Read the thread with mail_get_thread before drafting a reply in it.")
    allowed = ctx.participants[a.thread_id] - {ctx.mailbox.account}
    to = [addr.strip().lower() for addr in a.to]
    if not to:
        raise ToolError("A draft needs at least one recipient.")
    if outsiders := [addr for addr in to if addr not in allowed]:
        # Guardrail, not advice: injected text can't add a recipient (exfiltration), whatever the model believes.
        raise ToolError(f"Refused: {', '.join(outsiders)} isn't in this thread. You may only reply to: {', '.join(sorted(allowed))}.")
    if ctx.draft is None:
        ctx.draft = ctx.mailbox.create_draft(a.thread_id, to, a.subject, a.body)
    else:  # one draft per run: a second call revises it instead of leaving strays in Drafts
        ctx.draft = ctx.mailbox.update_draft(ctx.draft.id, a.thread_id, to, a.subject, a.body)
    return {"draft_id": ctx.draft.id, "status": "Saved as a draft for the user to review. You cannot send it."}


def finish(ctx: Context, a: FinishArgs) -> dict:
    if a.outcome == "drafted" and ctx.draft is None:
        raise ToolError("outcome 'drafted' needs a draft: call create_draft first, or choose another outcome.")
    ctx.finished = a.model_dump()
    return {"ok": True}


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    risk: Risk
    args: type[BaseModel]
    handler: Callable[[Context, BaseModel], dict]

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(self.name, f"[{self.risk}] {self.description}", self.args.model_json_schema())


TOOLS: dict[str, Tool] = {t.name: t for t in [
    Tool("search_memory", "Search the user's memories (things seen on their screen) for facts the reply needs.",
         "read", SearchMemoryArgs, search_memory),
    Tool("mail_search", "Find Gmail threads. Returns thread ids, subjects and participants.",
         "read", MailSearchArgs, mail_search),
    Tool("mail_get_thread", "Read every message in one thread. Required before drafting in it.",
         "read", GetThreadArgs, mail_get_thread),
    Tool("create_draft", "Save a reply in the thread as a Gmail draft for the user to review. Never sends.",
         "draft", DraftArgs, create_draft),
    Tool("finish", "End the task exactly once, with the outcome and a short summary for the user.",
         "read", FinishArgs, finish),
]}
assert not [t for t in TOOLS.values() if t.risk == "execute"], "execute tools must never be model-callable"


def run(ctx: Context, call: ToolCall) -> tuple[str, dict]:
    """Execute one call. Returns (status, result) where status is ok | error | refused."""
    tool = TOOLS.get(call.name)
    if tool is None:
        return "refused", {"error": f"Unknown tool {call.name!r}. Available: {', '.join(TOOLS)}."}
    try:
        args = tool.args.model_validate(call.args)
    except ValidationError as e:
        return "error", {"error": f"Invalid arguments: {e.errors(include_url=False)}"}
    try:
        return "ok", tool.handler(ctx, args)
    except ToolError as e:
        return "refused", {"error": str(e)}
    except MailboxError as e:
        return "error", {"error": str(e)}
