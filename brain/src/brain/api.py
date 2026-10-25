"""Local HTTP API for the Swift app. Listens on 127.0.0.1 only (CLAUDE.md safety rules).

Two guards, because any web page you visit can also send requests to localhost:
- a shared-secret token from a 0600 file that only your user account can read;
- a Host-header allowlist, which blocks DNS-rebinding attacks.
"""

import hmac
import json
import logging
import queue
import threading
import secrets
import sqlite3
from collections.abc import Iterator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel

from brain.agent import approval
from brain.agent.loop import close_loop
from brain.config import Settings, get_settings
from brain.db import store
from brain import episodes
from brain.ingest import ingest
from brain.loops import lifecycle, pipeline
from brain.loops.worker import DetectionWorker
from brain.llm.client import LLMClient
from brain.mailbox.base import MailboxError
from brain.mailbox.gmail import open_mailbox
from brain.models import ObservationIn

log = logging.getLogger(__name__)


def ensure_token(settings: Settings) -> str:
    path = settings.token_path
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.write_text(secrets.token_urlsafe(32))
    path.chmod(0o600)
    return path.read_text().strip()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.token = ensure_token(settings)
    store.connect(settings.db_path).close()  # run migrations once, up front
    worker = None
    if settings.auto_detect and settings.gemini_api_key:
        worker = DetectionWorker(settings)
        worker.start()
    app.state.worker = worker
    yield
    if worker:
        worker.stop()


app = FastAPI(title="Context Agent brain", lifespan=lifespan, docs_url=None, redoc_url=None)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])


def require_token(request: Request, x_brain_token: str = Header(default="")) -> None:
    if not hmac.compare_digest(x_brain_token, request.app.state.token):  # constant-time compare
        raise HTTPException(status_code=401, detail="missing or wrong X-Brain-Token")


def db() -> Iterator[sqlite3.Connection]:
    # One connection per request, never shared between requests. FastAPI may run this dependency's setup,
    # the endpoint and the teardown on different pool threads, hence check_same_thread=False.
    conn = store.connect(get_settings().db_path, check_same_thread=False)
    try:
        yield conn
    finally:
        conn.close()


class IngestResponse(BaseModel):
    status: Literal["stored", "duplicate", "near_duplicate"]
    observation_id: int | None
    new_lines: int | None
    redactions: dict[str, int]


class StatusResponse(BaseModel):
    ok: bool
    model: str
    auto_detect_running: bool
    observations: int
    captured: int
    pending: int
    failed: int
    open_loops: int
    last_capture_at: datetime | None
    last_error: str | None
    agent_ready: bool = False
    agent_detail: str = ""


@app.post("/observations", response_model=IngestResponse, dependencies=[Depends(require_token)])
def post_observation(obs: ObservationIn, conn: sqlite3.Connection = Depends(db)) -> IngestResponse:
    with conn:
        result = ingest(conn, obs, source="capture")
    log.info("capture %s · %s · %s", result.status, obs.app_name, obs.window_title[:60])
    return IngestResponse(status=result.status, observation_id=result.observation_id,
                          new_lines=result.new_lines, redactions=dict(result.redactions))


@app.get("/status", response_model=StatusResponse, dependencies=[Depends(require_token)])
def status(request: Request, conn: sqlite3.Connection = Depends(db)) -> StatusResponse:
    settings = get_settings()
    worker: DetectionWorker | None = request.app.state.worker
    c = store.counts(conn)
    last = conn.execute("SELECT MAX(captured_at) FROM observations WHERE source = 'capture'").fetchone()[0]
    return StatusResponse(
        ok=True, model=settings.llm_model,
        auto_detect_running=bool(worker and worker.is_alive()),
        observations=c["observations"], captured=c["captured"],
        pending=c["pending"],
        failed=c["failed"], open_loops=c["open_loops"],
        last_capture_at=datetime.fromisoformat(last) if last else None,
        last_error=worker.last_error if worker else None,
        **_agent_readiness(settings),
    )


def _agent_readiness(settings: Settings) -> dict:
    """Can "Close it for me" run? Checked locally (Keychain + config), with no network call."""
    import keyring

    from brain.mailbox.gmail import KEYCHAIN_ACCOUNT, KEYCHAIN_SERVICE
    if not keyring.get_password(KEYCHAIN_SERVICE, KEYCHAIN_ACCOUNT):
        return {"agent_ready": False, "agent_detail": "Gmail not connected: run `brain gmail-login`."}
    return {"agent_ready": True, "agent_detail": "Gmail connected"}


class LoopOut(BaseModel):
    id: int
    title: str
    direction: Literal["i_owe", "they_owe", "self"]
    counterparty: str
    deliverable: str
    note: str | None
    due_date: str | None
    state: str
    closed_reason: str | None
    confidence: float
    source_app: str | None
    bundle_id: str | None
    window_title: str | None
    quote: str | None
    seen: int
    updated_at: str
    last_action_id: int | None = None      # the latest "Close it for me" run, if any
    last_action_status: str | None = None
    proof_url: str | None = None           # closed by the agent: link to the sent email


class TransitionIn(BaseModel):
    to: Literal["closed", "dismissed", "open"]
    reason: str = "from the inbox"


@app.get("/loops", response_model=list[LoopOut], dependencies=[Depends(require_token)])
def list_loops(state: Literal["open", "closed", "all"] = "open", conn: sqlite3.Connection = Depends(db)) -> list[LoopOut]:
    """For the inbox: each loop with its source app, window and the quote that created it (like Minimi's cards)."""
    states = {"open": ("open", "acting", "awaiting_approval"), "closed": ("closed",), "all": None}[state]
    sql = """SELECT l.*, (SELECT COUNT(*) FROM loop_evidence e WHERE e.loop_id = l.id) AS seen,
                    (SELECT e.quote FROM loop_evidence e WHERE e.loop_id = l.id ORDER BY e.id LIMIT 1) AS quote,
                    (SELECT o.window_title FROM loop_evidence e JOIN observations o ON o.id = e.observation_id
                     WHERE e.loop_id = l.id ORDER BY e.id LIMIT 1) AS window_title,
                    (SELECT o.bundle_id FROM loop_evidence e JOIN observations o ON o.id = e.observation_id
                     WHERE e.loop_id = l.id ORDER BY e.id LIMIT 1) AS bundle_id,
                    (SELECT a.id FROM actions a WHERE a.loop_id = l.id AND a.kind = 'agent_run' ORDER BY a.id DESC LIMIT 1) AS run_id
             FROM loops l"""
    params: tuple = ()
    if states:
        sql += f" WHERE l.state IN ({','.join('?' * len(states))})"
        params = states
    sql += " ORDER BY l.due_date IS NULL, l.due_date, l.updated_at DESC"
    return [_loop_out(conn, r) for r in conn.execute(sql, params).fetchall()]


def _loop_out(conn: sqlite3.Connection, r: sqlite3.Row) -> LoopOut:
    fields = {k: r[k] for k in LoopOut.model_fields if k in r.keys()}
    if r["run_id"]:
        run = conn.execute("SELECT status, output_json FROM actions WHERE id = ?", (r["run_id"],)).fetchone()
        out = json.loads(run["output_json"] or "{}")
        fields.update(last_action_id=r["run_id"], last_action_status=run["status"])
        thread = out.get("sent_thread_id") or (out.get("draft") or {}).get("thread_id")
        if run["status"] == "sent" and thread:
            fields["proof_url"] = f"https://mail.google.com/mail/u/0/#all/{thread}"
    return LoopOut(**fields)


@app.post("/loops/{loop_id}/transition", response_model=LoopOut, dependencies=[Depends(require_token)])
def transition_loop(loop_id: int, body: TransitionIn, conn: sqlite3.Connection = Depends(db)) -> LoopOut:
    """Resolve, dismiss or reopen from the inbox. The user is the actor; "acting" and "awaiting_approval"
    belong to the agent (Phase 5), so the inbox can't set them."""
    try:
        with conn:
            lifecycle.transition(conn, loop_id, body.to, actor="user", reason=body.reason)
    except lifecycle.InvalidTransition as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return next(item for item in list_loops("all", conn) if item.id == loop_id)


# --- "Close it for me" (Phase 5) ----------------------------------------------

def mailbox(request: Request):
    """A fresh Gmail connection per run: Google's client (httplib2) isn't thread-safe, and FastAPI serves sync
    endpoints from a thread pool. Tests swap in a FakeMailbox via app.state.mailbox."""
    if getattr(request.app.state, "mailbox", None) is not None:
        return request.app.state.mailbox
    try:
        return open_mailbox(get_settings())
    except MailboxError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


class ActionOut(BaseModel):
    id: int
    loop_id: int | None
    status: str
    outcome: str | None
    summary: str | None
    draft: dict | None
    missing_info: list[str]
    steps: list[dict]


class ApproveIn(BaseModel):
    draft_hash: str              # hash of the draft the UI displayed: approve exactly what was seen
    body: str | None = None      # the body as edited in the UI, if changed
    to: list[str] | None = None  # recipients you typed (new emails only; a reply's are pinned to its thread)


class RejectIn(BaseModel):
    reason: str = "rejected in the inbox"


def _action_out(conn: sqlite3.Connection, action_id: int) -> ActionOut:
    row = conn.execute("SELECT * FROM actions WHERE id = ? AND kind = 'agent_run'", (action_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"no agent run #{action_id}")
    out = json.loads(row["output_json"] or "{}")
    return ActionOut(id=row["id"], loop_id=row["loop_id"], status=row["status"], outcome=out.get("outcome"),
                     summary=out.get("summary"), draft=out.get("draft"), missing_info=out.get("missing_info", []),
                     steps=out.get("steps", []))


@app.post("/loops/{loop_id}/close", response_model=ActionOut, dependencies=[Depends(require_token)])
def close_loop_endpoint(loop_id: int, request: Request, conn: sqlite3.Connection = Depends(db)) -> ActionOut:
    """Run the agent on one loop. It drafts at most; the result waits for /actions/{id}/approve."""
    settings = get_settings()
    llm = LLMClient(settings.gemini_api_key.get_secret_value(), settings.llm_model)
    try:
        run = close_loop(conn, llm, mailbox(request), settings, loop_id)
    except lifecycle.InvalidTransition as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return _action_out(conn, run.action_id)


@app.get("/actions/{action_id}", response_model=ActionOut, dependencies=[Depends(require_token)])
def get_action(action_id: int, conn: sqlite3.Connection = Depends(db)) -> ActionOut:
    return _action_out(conn, action_id)


@app.post("/actions/{action_id}/approve", response_model=ActionOut, dependencies=[Depends(require_token)])
def approve_action(action_id: int, body: ApproveIn, request: Request, conn: sqlite3.Connection = Depends(db)) -> ActionOut:
    """The only route that sends email, and only for the draft the user saw (ADR-012, ADR-046)."""
    try:
        approval.approve(conn, mailbox(request), action_id, shown_hash=body.draft_hash, edited_body=body.body,
                         edited_to=body.to)
    except approval.ApprovalError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return _action_out(conn, action_id)


@app.post("/actions/{action_id}/reject", response_model=ActionOut, dependencies=[Depends(require_token)])
def reject_action(action_id: int, body: RejectIn, request: Request, conn: sqlite3.Connection = Depends(db)) -> ActionOut:
    try:
        approval.reject(conn, mailbox(request), action_id, body.reason)
    except approval.ApprovalError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return _action_out(conn, action_id)


# --- Phase 6: the inbox UI ----------------------------------------------------

@app.post("/loops/{loop_id}/close/stream", dependencies=[Depends(require_token)])
def close_loop_stream(loop_id: int, request: Request):
    """Server-Sent Events (ADR-049): one `data: {json}` line per agent step, then the finished run.

    The agent runs in a worker thread with its own SQLite connection (connections can't cross threads),
    and pushes events into a queue that this response drains as they arrive.
    """
    settings = get_settings()
    box = mailbox(request)  # fail fast (503) before any state changes if Gmail isn't usable
    events: queue.Queue = queue.Queue()

    def work() -> None:
        conn = store.connect(settings.db_path)
        try:
            llm = getattr(request.app.state, "llm", None) or LLMClient(settings.gemini_api_key.get_secret_value(),
                                                                        settings.llm_model)
            run = close_loop(conn, llm, box, settings, loop_id, on_event=events.put)
            events.put({"type": "done", "action": _action_out(conn, run.action_id).model_dump()})
        except lifecycle.InvalidTransition as e:
            events.put({"type": "error", "detail": str(e)})
        except Exception as e:  # report, don't hang the stream
            log.exception("agent run failed")
            events.put({"type": "error", "detail": f"{type(e).__name__}: {e}"})
        finally:
            conn.close()
            events.put(None)

    threading.Thread(target=work, name=f"agent-{loop_id}", daemon=True).start()

    def stream():
        while (event := events.get()) is not None:
            yield f"data: {json.dumps(event, default=str)}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


class MemoryOut(BaseModel):
    id: int
    kind: str
    text: str
    app_name: str
    bundle_id: str
    happened_at: str


@app.get("/memories", response_model=list[MemoryOut], dependencies=[Depends(require_token)])
def recent_memories(limit: int = 20, conn: sqlite3.Connection = Depends(db)) -> list[MemoryOut]:
    rows = conn.execute(
        """SELECT m.id, m.kind, m.text, e.app_name, e.bundle_id, m.happened_at FROM memories m
           JOIN episodes e ON e.id = m.episode_id WHERE m.duplicate_of IS NULL
           ORDER BY m.happened_at DESC, m.id DESC LIMIT ?""", (min(limit, 100),)).fetchall()
    return [MemoryOut(**dict(r)) for r in rows]


class VisitIn(BaseModel):
    bundle_id: str
    window_title: str


@app.post("/visits/end", dependencies=[Depends(require_token)])
def end_visit(body: VisitIn, conn: sqlite3.Connection = Depends(db)) -> dict:
    """Sent by the app when you switch away from a window: process that visit now, not in 5 minutes."""
    with conn:
        episode_id = episodes.end_visit(conn, body.bundle_id, body.window_title)
    return {"closed_episode": episode_id}


class DeleteIn(BaseModel):
    confirm: str  # must be exactly "delete everything"


@app.post("/data/delete", dependencies=[Depends(require_token)])
def delete_all_data(body: DeleteIn, conn: sqlite3.Connection = Depends(db)) -> dict:
    """Settings → Delete all data: every capture, memory, vector, loop and audit row. The schema stays."""
    if body.confirm != "delete everything":
        raise HTTPException(status_code=400, detail='Send {"confirm": "delete everything"}.')
    tables = ["loop_transitions", "loop_evidence", "actions", "loop_vectors", "loops", "memory_vectors",
              "memory_embeddings", "memories", "embedding_cache", "observations", "episodes"]
    with conn:
        counts = {t: conn.execute(f"DELETE FROM {t}").rowcount for t in tables}
    conn.execute("VACUUM")  # actually reclaim the pages, so deleted text isn't left in the file
    return {"deleted": counts}

