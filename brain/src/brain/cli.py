"""`brain` command line: ingest → loops → close (the Phase 1 walking skeleton)."""

import json
import logging
from pathlib import Path

import typer
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from brain.agent.draft import draft_reply
from brain.config import get_settings
from brain.db import store
from brain.llm.client import LLMClient, LLMError, Usage
from brain.loops.detect import detect_loops
from brain.models import ObservationIn
from brain.redact import redact

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
    new = dupes = 0
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        obs_in = ObservationIn.model_validate_json(line)
        text, redactions = redact(obs_in.text)
        if redactions:
            console.print(f"[yellow]redacted[/] {dict(redactions)} in {_e(repr(obs_in.window_title))}")
        with conn:
            if store.insert_observation(conn, obs_in, text) is None:
                dupes += 1
            else:
                new += 1
    console.print(f"{new} new observation(s), {dupes} duplicate(s) skipped")
    if detect:
        _detect_pending(conn)


@app.command(name="detect")
def detect_cmd() -> None:
    """Run loop detection on observations that haven't been processed yet (e.g. after a failure)."""
    _detect_pending(_db())


def _detect_pending(conn) -> None:
    s = get_settings()
    llm = _llm()
    usages: list[Usage] = []
    created = merged = failed = 0
    pending = store.unprocessed_observations(conn)

    for obs in pending:
        console.print(f"[dim]{obs['captured_at'][:16]} {_e(obs['app_name'])} · {_e(obs['window_title'][:60])}[/]")
        try:
            candidates, usage = detect_loops(llm, obs, name=s.user_name, email=s.user_email)
        except LLMError as e:
            failed += 1
            console.print(f"  [red]detection failed:[/] {_e(e)}")
            continue
        usages.append(usage)
        with conn:  # one transaction per observation: its loops + processed flag, or nothing
            for c in candidates:
                existing = store.find_open_loop_by_quote(conn, c.evidence_quote)
                if existing:
                    store.add_evidence(conn, existing, obs["id"], c.evidence_quote, "progress")
                    merged += 1
                    console.print(f"  [blue]↺[/] seen again → loop #{existing}")
                else:
                    loop_id = store.create_loop(conn, observation_id=obs["id"], **c.model_dump())
                    created += 1
                    console.print(f"  [green]+[/] loop #{loop_id}: {_e(c.title)} [dim]({c.confidence:.2f})[/]")
            store.mark_processed(conn, obs["id"])

    console.print(f"\nProcessed {len(pending) - failed}/{len(pending)} · "
                  f"{created} loop(s) created, {merged} merged into existing"
                  + (f" · [red]{failed} failed, run `brain detect` to retry[/]" if failed else ""))
    _print_usage(usages)


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
        who = ("→ " if r["direction"] == "i_owe" else "← ") + _e(r["counterparty"])
        table.add_row(str(r["id"]), who, _e(r["title"]), r["due_date"] or "—", f"{r['confidence']:.2f}",
                      f"{r['evidence_count']}×", r["state"])
    console.print(table)
    console.print("[dim]→ you owe them · ← they owe you[/]")


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
