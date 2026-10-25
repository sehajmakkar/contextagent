"""Retrieval eval: Recall@5, MRR, and latency for each search mode (ADR-009, ADR-015).

    uv run python -m evals.run_retrieval            # reuse the cached memory set
    uv run python -m evals.run_retrieval --rebuild  # re-extract memories from the fixtures

Labels name the fixture observation(s) that answer each query, not memory IDs: extraction is an LLM step,
so memory IDs and wording change between builds, while provenance (memory → source observation) doesn't.
A query whose source produced no memory counts as an *extraction miss*, separate from retrieval quality.
"""

import json
import shutil
import statistics
import sys
import time
from datetime import date
from pathlib import Path

from brain.config import REPO_ROOT, get_settings
from brain.db import store
from brain.ingest import ingest
from brain.llm.client import LLMClient
from brain.loops import pipeline
from brain.memory import retrieve
from brain.memory.embed import QUERY_PREFIX, embed_memories, vector_for
from brain.models import ObservationIn

FIXTURES = [REPO_ROOT / "fixtures/sessions/demo_week.jsonl", REPO_ROOT / "fixtures/sessions/memory_week.jsonl"]
QUERIES = Path(__file__).parent / "datasets/retrieval.jsonl"
MODES = ["bm25", "vector", "hybrid", "hybrid_recency"]
K = 5


def build(settings, llm, rebuild: bool):
    if rebuild and settings.data_dir.exists():
        shutil.rmtree(settings.data_dir)
    conn = store.connect(settings.db_path)
    if conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0] == 0:
        print(f"Building the memory set with {settings.llm_model} (one-time)…")
        for path in FIXTURES:
            for line in path.read_text().splitlines():
                with conn:
                    ingest(conn, ObservationIn.model_validate_json(line), "file")
        for episode in pipeline.pending(conn, settings):
            outcome = pipeline.process(conn, llm, episode, settings)
            if outcome.quota_exhausted:
                sys.exit(f"Stopped: {outcome.error}. Re-run later; finished episodes are kept.")
    embed_memories(conn, llm, settings)
    return conn


def relevant_ids(conn, captured_at: list[str]) -> set[int]:
    marks = ",".join("?" * len(captured_at))
    rows = conn.execute(f"""SELECT m.id FROM memories m JOIN observations o ON o.id = m.observation_id
                            WHERE o.captured_at IN ({marks}) AND m.duplicate_of IS NULL""", captured_at)
    return {r["id"] for r in rows}


def main() -> None:
    base = get_settings()
    settings = base.model_copy(update={"data_dir": Path(__file__).parent / ".cache" / base.llm_model})
    llm = LLMClient(settings.gemini_api_key.get_secret_value(), settings.llm_model)
    conn = build(settings, llm, "--rebuild" in sys.argv)
    queries = [json.loads(line) for line in QUERIES.read_text().splitlines() if line.strip()]

    # Embed every query first and time it, so search latency below is purely local.
    embed_ms = []
    for q in queries:
        t0 = time.perf_counter()
        _, called = vector_for(conn, llm, QUERY_PREFIX.format(text=q["query"]), settings)
        if called:
            embed_ms.append((time.perf_counter() - t0) * 1000)

    answerable = [q for q in queries if relevant_ids(conn, q["relevant_captured_at"])]
    results, misses = {}, {m: [] for m in MODES}
    for mode in MODES:
        hits, top1, rr, latency = 0, 0, [], []
        for q in answerable:
            wanted = relevant_ids(conn, q["relevant_captured_at"])
            t0 = time.perf_counter()
            ranked = [h.memory_id for h in retrieve.search(conn, llm, settings, q["query"], k=10, mode=mode)]
            latency.append((time.perf_counter() - t0) * 1000)
            rank = next((i for i, m in enumerate(ranked, start=1) if m in wanted), None)
            hits += bool(rank and rank <= K)
            top1 += rank == 1
            rr.append(1 / rank if rank else 0.0)
            if not rank or rank > K:
                misses[mode].append(q["query"])
        latency.sort()
        results[mode] = (hits / len(answerable), statistics.mean(rr), statistics.median(latency),
                         latency[int(0.95 * (len(latency) - 1))], top1 / len(answerable))

    memories = conn.execute("SELECT COUNT(*), SUM(duplicate_of IS NOT NULL) FROM memories").fetchone()
    lines = [
        f"# Retrieval eval: {date.today()}",
        "",
        f"Memory set: {memories[0]} memories ({memories[1]} folded as duplicates) extracted by `{settings.llm_model}` "
        f"from {len(FIXTURES)} synthetic fixture weeks. Embeddings: `{settings.embed_model}` @ {settings.embed_dims} dims.",
        f"Queries: {len(queries)} labelled, **{len(answerable)} answerable** "
        f"({len(queries) - len(answerable)} extraction miss(es): the source produced no memory).",
        "",
        f"| Mode | Recall@1 | Recall@{K} | MRR@10 | p50 search | p95 search |",
        "|---|---|---|---|---|---|",
        *[f"| {m} | {r[4]:.0%} ({round(r[4] * len(answerable))}/{len(answerable)}) | {r[0]:.0%} | {r[1]:.3f} | {r[2]:.1f} ms | {r[3]:.1f} ms |"
          for m, r in results.items()],
        "",
        f"Query embedding (network, uncached): {len(embed_ms)} call(s)"
        + (f", p50 {statistics.median(embed_ms):.0f} ms, max {max(embed_ms):.0f} ms." if embed_ms else " (all cached)."),
        "Search latency is local only: query vectors are cached before timing.",
        "",
        "## Misses (not in the top 5)",
        *[f"- **{m}**: " + ("; ".join(misses[m]) or "none") for m in MODES],
        "",
        "## Extraction misses",
        *([f"- {q['query']}" for q in queries if q not in answerable] or ["- none"]),
    ]
    report = "\n".join(lines) + "\n"
    out = Path(__file__).parent / "results" / "retrieval.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text(report)
    print(report)


if __name__ == "__main__":
    main()
