"""`brain` command line: ingest → loops → close, plus `serve` for the Swift app."""

import json
import logging
import time
from datetime import UTC, datetime
from collections import Counter
from pathlib import Path

import typer
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from brain.agent.draft import draft_reply
from brain.config import get_settings
from brain.db import store
from brain import episodes, retention
from brain.ingest import ingest as ingest_observation
from brain.llm.client import LLMClient, LLMError, Usage
from brain.loops import lifecycle, pipeline
from brain.memory import embed as embedding
from brain.memory import retrieve
from brain.models import ObservationIn

app = typer.Typer(no_args_is_help=True, add_completion=False)
console = Console()


def _e(value: object) -> str:
    """Escape untrusted text (screen content, model output) so Rich can't read it as markup."""
    return escape(str(value))


@app.callback()
def main(verbose: bool = typer.Option(False, "--verbose", "-v", help="Log every LLM call.")) -> None:
    logging.basicConfig(level=logging.INFO if verbose else logging.WARNING, format="%(levelname)s %(name)s: %(message)s")


def _db():
    return store.connect(get_settings().db_path)


def _llm() -> LLMClient:
    s = get_settings()
    if not s.gemini_api_key:
        console.print("[red]GEMINI_API_KEY is not set.[/] Copy .env.example to .env and add your key.")
        raise typer.Exit(1)
    return LLMClient(s.gemini_api_key.get_secret_value(), s.llm_model)


def _print_usage(usages: list[Usage]) -> None:
    if usages:
        console.print(
            f"[dim]{len(usages)} LLM call(s) · prompt {sum(u.prompt_tokens for u in usages):,} tok · "
            f"output {sum(u.output_tokens for u in usages):,} tok · thinking {sum(u.thinking_tokens for u in usages):,} tok · "
            f"{sum(u.latency_ms for u in usages) / 1000:.1f}s[/]"
        )


@app.command()
def ingest(
    path: Path = typer.Argument(..., exists=True, help="JSONL file of observations."),
    detect: bool = typer.Option(True, help="Run loop detection on new observations."),
) -> None:
    """Store observations (redacted, deduplicated), then detect open loops in new ones."""
    conn = _db()
    tally: Counter[str] = Counter()
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        obs_in = ObservationIn.model_validate_json(line)
        with conn:
            result = ingest_observation(conn, obs_in, source="file")
        tally[result.status] += 1
        if result.redactions:
            console.print(f"[yellow]redacted[/] {dict(result.redactions)} in {_e(repr(obs_in.window_title))}")
    console.print(f"{tally['stored']} new observation(s), {tally['duplicate']} duplicate(s), "
                  f"{tally['near_duplicate']} near-duplicate(s) skipped")
    if detect:
        _detect_pending(conn)


@app.command(name="process")
def process_cmd(close_now: bool = typer.Option(False, "--close-now",
                                              help="Treat every open episode as finished (for testing; skips the 5-min wait).")) -> None:
    """Process closed episodes that haven't been processed yet: memories + loops (also retries failures)."""
    conn = _db()
    if close_now:
        with conn:
            n = episodes.close_stale(conn, current=datetime.max.replace(tzinfo=UTC))
        console.print(f"[dim]Closed {n} open episode(s) early.[/]")
    _detect_pending(conn)


@app.command(name="detect", hidden=True)
def detect_cmd() -> None:
    """Old name for `process`."""
    _detect_pending(_db())


def _detect_pending(conn) -> None:
    s = get_settings()
    llm = _llm()
    usages: list[Usage] = []
    created = merged = failed = skipped = memories = 0
    todo = pipeline.pending(conn, s)

    for ep in todo:
        console.print(f"[dim]{ep['started_at'][:16]} {_e(ep['app_name'])} · {_e(ep['window_title'][:55])} "
                      f"({ep['observation_count']} snapshot(s), {len(ep['text']):,} chars)[/]")
        outcome = pipeline.process(conn, llm, ep, s)
        if outcome.quota_exhausted:
            console.print(f"[red]{_e(outcome.error)}.[/] Stopping; the rest stay pending for `brain process`.")
            break
        if outcome.error:
            failed += 1
            console.print(f"  [red]failed:[/] {_e(outcome.error)}")
            continue
        if outcome.skipped:
            skipped += 1
            console.print(f"  [dim]skipped: {outcome.skipped}[/]")
            continue
        usages.extend(outcome.usages)
        for text in outcome.memories:
            console.print(f"  [magenta]•[/] {_e(text)}")
        for loop_id in outcome.merged:
            console.print(f"  [blue]↺[/] seen again → loop #{loop_id}")
        for loop_id in outcome.closed:
            console.print(f"  [green]✓[/] loop #{loop_id} closed (inferred from this screen)")
        for loop_id in outcome.progressed:
            console.print(f"  [blue]…[/] progress on loop #{loop_id}")
        for loop_id, title, confidence in outcome.created:
            console.print(f"  [green]+[/] loop #{loop_id}: {_e(title)} [dim]({confidence:.2f})[/]")
        created += len(outcome.created)
        merged += len(outcome.merged)
        memories += len(outcome.memories)

    console.print(f"\nEpisodes {len(todo) - failed}/{len(todo)} processed ({skipped} skipped by the local gate) · "
                  f"{memories} memories · {created} loop(s) created, {merged} merged"
                  + (f" · [red]{failed} failed, run `brain process` to retry[/]" if failed else ""))
    if held := pipeline.held_back(conn, s):
        console.print(f"[yellow]{held} live-capture episode(s) held back:[/] free tier, ALLOW_FREE_TIER_LIVE is off (ADR-027)")
    _print_usage(usages)
    if memories:
        _embed(conn, llm)


def _embed(conn, llm) -> None:
    try:
        out = embedding.embed_memories(conn, llm, get_settings())
    except LLMError as e:
        console.print(f"[red]Embedding stopped:[/] {_e(e)}. Run `brain embed` later.")
        return
    console.print(f"[dim]Embedded {out.embedded} memor{'y' if out.embedded == 1 else 'ies'} "
                  f"({out.api_calls} API call(s)), {out.duplicates} near-duplicate(s) folded into earlier ones[/]")


@app.command(name="embed")
def embed_cmd() -> None:
    """Embed memories that have no vector yet (backfill, or after a failure)."""
    _embed(_db(), _llm())


@app.command()
def search(query: str, k: int = typer.Option(5, "-k"),
           mode: str = typer.Option("hybrid", help="bm25, vector, hybrid or hybrid_recency")) -> None:
    """Search memories. bm25 works offline; the others embed the query."""
    conn = _db()
    llm = None if mode == "bm25" else _llm()
    started = time.perf_counter()
    hits = retrieve.search(conn, llm, get_settings(), query, k=k, mode=mode)
    ms = (time.perf_counter() - started) * 1000
    if not hits:
        console.print("No matching memories.")
    for rank, h in enumerate(hits, start=1):
        console.print(f"[bold]{rank}.[/] [cyan]{h.kind}[/] {_e(h.text)}")
        console.print(f"    [dim]#{h.memory_id} · {h.happened_at[:16]} · {_e(h.app_name)} · {_e(h.window_title[:50])} · score {h.score:.4f}[/]")
    console.print(f"[dim]{mode} · {ms:.0f} ms[/]")


@app.command()
def memories(query: str = typer.Argument("", help="Optional keyword filter (FTS5)."),
             limit: int = typer.Option(30)) -> None:
    """List extracted memories, newest first, with where each came from."""
    conn = _db()
    if query:
        rows = conn.execute(
            """SELECT m.*, e.app_name, e.window_title FROM memories_fts f JOIN memories m ON m.id = f.rowid
               JOIN episodes e ON e.id = m.episode_id WHERE memories_fts MATCH ? ORDER BY rank LIMIT ?""",
            (query, limit)).fetchall()
    else:
        rows = conn.execute(
            """SELECT m.*, e.app_name, e.window_title FROM memories m JOIN episodes e ON e.id = m.episode_id
               ORDER BY m.happened_at DESC, m.id DESC LIMIT ?""", (limit,)).fetchall()
    if not rows:
        console.print("No memories yet. Run [bold]brain process[/].")
        return
    for r in rows:
        console.print(f"[bold]#{r['id']}[/] [cyan]{r['kind']}[/] {_e(r['text'])}")
        console.print(f"    [dim]{r['happened_at'][:16]} · {_e(r['app_name'])} · {_e(r['window_title'][:50])}[/]")


@app.command()
def funnel(source: str = typer.Option("all", help="all, capture (your live screen) or file (fixtures).")) -> None:
    """How much text survives each stage, from raw snapshots to memories (the shrink-first funnel)."""
    conn = _db()
    with conn:
        if backfilled := episodes.backfill(conn):
            console.print(f"[dim]Grouped {backfilled} older snapshot(s) into episodes (local only).[/]")
    where = "" if source == "all" else f" WHERE source = '{'capture' if source == 'capture' else 'file'}'"
    obs = conn.execute(f"SELECT COUNT(*), COALESCE(SUM(raw_chars), 0) FROM episodes{where}").fetchone()
    eps = conn.execute(f"""SELECT COUNT(*), COALESCE(SUM(LENGTH(text)), 0),
                                 COALESCE(SUM(skipped_reason IS NOT NULL), 0),
                                 COALESCE(SUM(llm_calls), 0), COALESCE(SUM(prompt_tokens), 0),
                                 COALESCE(SUM(output_tokens), 0), COALESCE(SUM(thinking_tokens), 0),
                                 COALESCE(SUM(observation_count), 0)
                          FROM episodes{where}""").fetchone()
    mem = conn.execute(f"""SELECT COUNT(*), COALESCE(SUM(LENGTH(m.text)), 0) FROM memories m
                           JOIN episodes e ON e.id = m.episode_id{where.replace('source', 'e.source')}""").fetchone()
    table = Table(title="Shrink-first funnel")
    for col in ("Stage", "Items", "Chars", "vs raw"):
        table.add_column(col, justify="right" if col != "Stage" else "left")
    raw = obs[1] or 1
    table.add_row("Snapshots stored", f"{eps[7]:,}", f"{obs[1]:,}", "100%")
    table.add_row("Episodes (lines merged)", f"{eps[0]:,}", f"{eps[1]:,}", f"{eps[1] / raw:.0%}")
    table.add_row("  sent to the LLM", f"{eps[0] - eps[2]:,}", "", "")
    table.add_row("Memories kept", f"{mem[0]:,}", f"{mem[1]:,}", f"{mem[1] / raw:.1%}")
    console.print(table)
    console.print(f"[dim]{eps[3]} LLM call(s) · prompt {eps[4]:,} tok · output {eps[5]:,} tok · thinking {eps[6]:,} tok · "
                  f"{eps[2]} episode(s) skipped by the local gate[/]")


@app.command()
def purge(days: int = typer.Option(7, help="Erase raw snapshot text older than this, once processed.")) -> None:
    """Retention: erase old raw snapshot text. Memories and loop evidence are kept."""
    conn = _db()
    with conn:
        erased = retention.purge(conn, older_than_days=days)
    console.print(f"Erased the raw text of {erased} processed snapshot(s) older than {days} day(s).")


@app.command()
def serve(reload: bool = typer.Option(False, help="Restart on code changes (dev).")) -> None:
    """Run the local API for the Swift app on 127.0.0.1, with background loop detection."""
    import uvicorn

    s = get_settings()
    if not s.live_detection_allowed:
        console.print("[yellow]Free tier:[/] live captures are stored locally but NOT sent to Gemini (ADR-027).")
    else:
        console.print(f"[bold red]Live detection is on[/] ({s.gemini_tier} tier). Captured screen text goes to Gemini.")
    uvicorn.run("brain.api:app", host="127.0.0.1", port=s.port, reload=reload, log_level="info")


@app.command()
def captures(limit: int = typer.Option(10, help="How many to show."),
             full: bool = typer.Option(False, help="Print the full captured text.")) -> None:
    """Show the latest live captures: exactly what was read from your screen."""
    rows = _db().execute(
        "SELECT * FROM observations WHERE source = 'capture' ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    if not rows:
        console.print("No live captures yet. Start [bold]brain serve[/] and the menu-bar app.")
        return
    for r in rows:
        state = "processed" if r["processed_at"] else ("failed" if r["detect_attempts"] >= 3 else "pending")
        console.print(f"[bold]#{r['id']}[/] {r['captured_at'][:19]} · {_e(r['app_name'])} · "
                      f"{_e(r['window_title'][:70])} [dim]({len(r['text']):,} chars, {state})[/]")
        if r["url"]:
            console.print(f"   [dim]{_e(r['url'][:100])}[/]")
        body = r["text"] if full else r["text"][:300] + ("…" if len(r["text"]) > 300 else "")
        console.print(Panel(_e(body), expand=False))


@app.command()
def loops(all: bool = typer.Option(False, "--all", help="Include closed and dismissed loops.")) -> None:
    """List open loops, soonest due first."""
    rows = store.list_loops(_db(), state=None if all else "open")
    if not rows:
        console.print("No loops yet. Run [bold]brain ingest <file>[/] first.")
        return
    table = Table(title="Open loops" if not all else "All loops")
    for col in ("#", "Who", "Loop", "Due", "Conf", "Seen", "State"):
        table.add_column(col)
    for r in rows:
        who = {"i_owe": "→ ", "they_owe": "← ", "self": "• "}[r["direction"]] + _e(r["counterparty"])
        table.add_row(str(r["id"]), who, _e(r["title"]), r["due_date"] or "—", f"{r['confidence']:.2f}",
                      f"{r['evidence_count']}×", r["state"])
    console.print(table)
    console.print("[dim]→ you owe them · ← they owe you · • reminder to yourself[/]")


@app.command()
def show(loop_id: int) -> None:
    """Show a loop and the evidence behind it."""
    conn = _db()
    loop = store.get_loop(conn, loop_id)
    if not loop:
        console.print(f"[red]No loop #{loop_id}[/]")
        raise typer.Exit(1)
    console.print(Panel(
        f"[bold]{_e(loop['title'])}[/]\n{loop['direction']} · {_e(loop['counterparty'])} "
        f"{_e(loop['counterparty_email'] or '')}\nOwed: {_e(loop['deliverable'])} · Due: {loop['due_date'] or '—'} · "
        f"State: {loop['state']} · Confidence: {loop['confidence']:.2f}",
        title=f"Loop #{loop_id}",
    ))
    for e in store.get_evidence(conn, loop_id):
        console.print(f"  {_e('[' + e['kind'] + ']')} {e['captured_at']} · {_e(e['app_name'])} · {_e(e['window_title'])}")
        console.print(f"    “{_e(e['quote'])}”")


def _transition(loop_id: int, to: str, reason: str) -> None:
    conn = _db()
    try:
        with conn:
            lifecycle.transition(conn, loop_id, to, actor="user", reason=reason)
    except lifecycle.InvalidTransition as e:
        console.print(f"[red]{_e(e)}[/]")
        raise typer.Exit(1)
    console.print(f"Loop #{loop_id} → {to}")


@app.command()
def resolve(loop_id: int, note: str = typer.Option("resolved by you", help="Why it's done.")) -> None:
    """Mark a loop done yourself (Minimi's "Resolve")."""
    _transition(loop_id, "closed", note)


@app.command()
def dismiss(loop_id: int, note: str = typer.Option("not a loop", help="Why it isn't a loop.")) -> None:
    """Not a real loop. Dismissals are labelled examples for the loop eval."""
    _transition(loop_id, "dismissed", note)


@app.command()
def reopen(loop_id: int, note: str = typer.Option("reopened by you")) -> None:
    """Undo a close or a dismissal (e.g. an inferred close that was wrong)."""
    _transition(loop_id, "open", note)


@app.command()
def history(loop_id: int) -> None:
    """Every state change of a loop: who made it, why, and on what evidence."""
    rows = lifecycle.history(_db(), loop_id)
    if not rows:
        console.print(f"[red]No loop #{loop_id}[/]")
        raise typer.Exit(1)
    for h in rows:
        conf = f" ({h['confidence']:.2f})" if h["confidence"] is not None else ""
        console.print(f"{h['created_at'][:19]}  {h['from_state'] or '·'} → [bold]{h['to_state']}[/]  "
                      f"[cyan]{h['actor']}[/]{conf}  {_e(h['reason'])}")


@app.command()
def close(loop_id: int) -> None:
    """Draft the email that would close this loop (nothing is sent)."""
    s = get_settings()
    conn = _db()
    loop = store.get_loop(conn, loop_id)
    if not loop:
        console.print(f"[red]No loop #{loop_id}[/]")
        raise typer.Exit(1)
    evidence = store.get_evidence(conn, loop_id)
    with console.status("Drafting…"):
        try:
            draft, removed, usage = draft_reply(_llm(), loop, evidence, name=s.user_name, email=s.user_email)
        except LLMError as e:
            console.print(f"[red]Drafting failed:[/] {_e(e)}")
            raise typer.Exit(1)

    with conn:
        action_id = store.log_action(
            conn, loop_id=loop_id, kind="draft_reply", status="drafted",
            input={"loop_id": loop_id, "observation_ids": [e["observation_id"] for e in evidence]},
            output=draft.model_dump(), model=usage.model,
            prompt_tokens=usage.prompt_tokens, output_tokens=usage.output_tokens,
            thinking_tokens=usage.thinking_tokens,
        )

    console.print(Panel(
        f"[bold]To:[/] {_e(', '.join(draft.to)) or '[red](no known recipient)[/]'}\n"
        f"[bold]Subject:[/] {_e(draft.subject)}\n\n{_e(draft.body)}",
        title=f"Draft for loop #{loop_id} · action #{action_id}", subtitle="not sent",
    ))
    if draft.missing_info:
        console.print("[yellow]Needs info the agent doesn't have yet:[/] " + _e("; ".join(draft.missing_info)))
    if removed:
        console.print(f"[red]Removed recipients not found in the thread:[/] {_e(', '.join(removed))}")
    _print_usage([usage])


@app.command()
def reset(yes: bool = typer.Option(False, "--yes", help="Skip the confirmation.")) -> None:
    """Delete the local database (all observations, loops and drafts)."""
    path = get_settings().db_path
    if not yes:
        typer.confirm(f"Delete {path}?", abort=True)
    for p in (path, path.with_name(path.name + "-wal"), path.with_name(path.name + "-shm")):
        p.unlink(missing_ok=True)
    console.print(f"Deleted {path}")


@app.command()
def where() -> None:
    """Print where data lives and which model is configured."""
    s = get_settings()
    console.print(json.dumps({"db": str(s.db_path), "model": s.llm_model, "tier": s.gemini_tier,
                              "api_key_set": bool(s.gemini_api_key)}, indent=2))
