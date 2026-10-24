"""Local HTTP API for the Swift app. Listens on 127.0.0.1 only (CLAUDE.md safety rules).

Two guards, because any web page you visit can also send requests to localhost:
- a shared-secret token from a 0600 file that only your user account can read;
- a Host-header allowlist, which blocks DNS-rebinding attacks.
"""

import hmac
import logging
import secrets
import sqlite3
from collections.abc import Iterator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel

from brain.config import Settings, get_settings
from brain.db import store
from brain.ingest import ingest
from brain.loops import pipeline
from brain.loops.worker import DetectionWorker
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
    # One connection per request: FastAPI runs sync endpoints on a thread pool.
    conn = store.connect(get_settings().db_path)
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
    tier: Literal["free", "paid"]
    live_detection_allowed: bool
    auto_detect_running: bool
    observations: int
    captured: int
    pending: int
    held_back: int
    failed: int
    open_loops: int
    last_capture_at: datetime | None
    last_error: str | None


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
        ok=True, model=settings.llm_model, tier=settings.gemini_tier,
        live_detection_allowed=settings.live_detection_allowed,
        auto_detect_running=bool(worker and worker.is_alive()),
        observations=c["observations"], captured=c["captured"],
        pending=c["pending"] - pipeline.held_back(conn, settings), held_back=pipeline.held_back(conn, settings),
        failed=c["failed"], open_loops=c["open_loops"],
        last_capture_at=datetime.fromisoformat(last) if last else None,
        last_error=worker.last_error if worker else None,
    )
