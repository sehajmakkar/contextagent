"""Loop eval: precision / recall / F1 for new loops, due-date accuracy, and closes (ADR-015, ADR-042).

    uv run python -m evals.run_loops                 # uses cached model outputs where present
    uv run python -m evals.run_loops --fresh         # call the model again for every item
    uv run python -m evals.run_loops --limit 18      # first N items (e.g. to fit a small daily quota)
    uv run python -m evals.run_loops --dataset loops_holdout.jsonl   # held-out set: score, never tune on it

Model output is cached per (model, item), so re-scoring and threshold sweeps cost no API calls.
"""

import json
import sys
from datetime import date
from pathlib import Path

from brain.config import get_settings
from brain.llm.client import LLMClient, QuotaExhausted
from brain.loops.detect import CLOSE_CONFIDENCE, MIN_CONFIDENCE, LoopAnalysis, analyze_loops
from brain.loops.verify import verify_close

HERE = Path(__file__).parent
THRESHOLDS = [0.5, 0.6, 0.7, 0.8, 0.9]


def matches(expected: dict, predicted) -> bool:
    if expected["direction"] != predicted.direction:
        return False
    who = expected["counterparty"].lower()
    return who in ("*", "self") or who in predicted.counterparty.lower()


def score(items, outputs, threshold):
    tp = fp = fn = due_ok = due_total = 0
    errors = []
    for item in items:
        predicted = [c for c in outputs[item["id"]].new_loops if c.confidence >= threshold]
        unmatched = list(predicted)
        for exp in item["expected_new"]:
            hit = next((p for p in unmatched if matches(exp, p)), None)
            if hit is None:
                fn += 1
                errors.append(f"{item['id']}: missed {exp['direction']} {exp['counterparty']} ({item['note'] or '-'})")
                continue
            unmatched.remove(hit)
            tp += 1
            if exp["due_date"]:
                due_total += 1
                due_ok += str(hit.due_date) == exp["due_date"]
        for extra in unmatched:
            fp += 1
            errors.append(f"{item['id']}: false loop '{extra.title}' ({extra.direction}, {extra.confidence:.2f}) "
                          f"({item['note'] or '-'})")
    p = tp / (tp + fp) if tp + fp else 1.0
    r = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * p * r / (p + r) if p + r else 0.0
    return dict(tp=tp, fp=fp, fn=fn, precision=p, recall=r, f1=f1, due_ok=due_ok, due_total=due_total), errors


def proposed_closes(output) -> set[int]:
    return {u.loop_id for u in output.updates if u.status == "done" and u.confidence >= CLOSE_CONFIDENCE}


def score_closes(items, outputs, verified=None):
    """verified=None scores what the analysis call proposed; otherwise only closes the verifier confirmed."""
    tp = fp = fn = 0
    errors = []
    for item in items:
        closed = proposed_closes(outputs[item["id"]])
        if verified is not None:
            closed = {i for i in closed if verified.get(f"{item['id']}:{i}")}
        expected = set(item["expected_closed"])
        tp += len(closed & expected)
        fn += len(expected - closed)
        fp += len(closed - expected)
        for loop_id in closed - expected:
            errors.append(f"{item['id']}: UNSAFE close of #{loop_id} ({item['note']})")
        for loop_id in expected - closed:
            errors.append(f"{item['id']}: missed close of #{loop_id} ({item['note']})")
    return dict(tp=tp, fp=fp, fn=fn), errors


def main() -> None:
    settings = get_settings()
    dataset = HERE / "datasets" / (sys.argv[sys.argv.index("--dataset") + 1] if "--dataset" in sys.argv else "loops.jsonl")
    items = [json.loads(line) for line in dataset.read_text().splitlines() if line.strip()]
    if "--limit" in sys.argv:
        items = items[: int(sys.argv[sys.argv.index("--limit") + 1])]
    cache_path = HERE / ".cache" / f"{dataset.stem}-{settings.llm_model}.json"
    cache = {} if "--fresh" in sys.argv or not cache_path.exists() else json.loads(cache_path.read_text())
    llm = LLMClient(settings.gemini_api_key.get_secret_value(), settings.llm_model)

    outputs, calls = {}, 0
    for item in items:
        if item["id"] not in cache:
            try:
                analysis, _ = analyze_loops(llm, item["observation"], item["tracked"],
                                            name=settings.user_name, email="sehaj.demo@example.com")
            except QuotaExhausted as e:
                sys.exit(f"Stopped after {calls} call(s): {e}. Cached results are kept; re-run later.")
            cache[item["id"]] = analysis.model_dump(mode="json")
            calls += 1
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(cache, indent=1))
        outputs[item["id"]] = LoopAnalysis.model_validate(cache[item["id"]])
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    # Verify every proposed close, as production does (cached like the analysis).
    verified = {}
    for item in items:
        tracked = {t["id"]: t for t in item["tracked"]}
        for u in outputs[item["id"]].updates:
            key = f"{item['id']}:{u.loop_id}"
            if u.status != "done" or u.confidence < CLOSE_CONFIDENCE:
                continue
            if f"verify:{key}" not in cache:
                try:
                    ok, _, _ = verify_close(llm, tracked[u.loop_id], u.evidence_quote, item["observation"]["text"])
                except QuotaExhausted as e:
                    sys.exit(f"Stopped after {calls} call(s): {e}. Cached results are kept; re-run later.")
                cache[f"verify:{key}"] = ok
                calls += 1
                cache_path.write_text(json.dumps(cache, indent=1))
            verified[key] = cache[f"verify:{key}"]

    main_score, errors = score(items, outputs, MIN_CONFIDENCE)
    proposed, _ = score_closes(items, outputs)
    closes, close_errors = score_closes(items, outputs, verified)
    negatives = [i for i in items if not i["expected_new"] and not i["expected_closed"]]
    clean = sum(1 for i in negatives if not [c for c in outputs[i["id"]].new_loops if c.confidence >= MIN_CONFIDENCE]
                and not [x for x in proposed_closes(outputs[i["id"]]) if verified.get(f"{i['id']}:{x}")])

    s = main_score
    lines = [
        f"# Loop eval ({dataset.stem}): {date.today()} · `{settings.llm_model}`",
        "",
        f"{len(items)} labelled screens ({sum(len(i['expected_new']) for i in items)} expected new loops, "
        f"{sum(len(i['expected_closed']) for i in items)} expected closes, {len(negatives)} negatives). "
        f"{calls} new API call(s) this run; the rest came from the cache.",
        "",
        f"## New loops (confidence ≥ {MIN_CONFIDENCE})",
        f"Precision **{s['precision']:.0%}** ({s['tp']}/{s['tp'] + s['fp']}) · Recall **{s['recall']:.0%}** "
        f"({s['tp']}/{s['tp'] + s['fn']}) · F1 **{s['f1']:.2f}** · due date right {s['due_ok']}/{s['due_total']}",
        f"Negatives left clean (no false loop or close): {clean}/{len(negatives)}",
        "",
        "## Closes (inferred done, confidence ≥ %.1f)" % CLOSE_CONFIDENCE,
        f"Proposed by the analysis call: correct {proposed['tp']}/{proposed['tp'] + proposed['fn']}, unsafe {proposed['fp']}",
        f"**After the verifier: correct {closes['tp']}/{closes['tp'] + closes['fn']} · unsafe closes {closes['fp']}** "
        "(closing a loop that isn't done hides it from you)",
        "",
        "## Threshold sweep (new loops)",
        "| min confidence | precision | recall | F1 |",
        "|---|---|---|---|",
        *[f"| {t} | {r['precision']:.0%} | {r['recall']:.0%} | {r['f1']:.2f} |"
          for t in THRESHOLDS for r in [score(items, outputs, t)[0]]],
        "",
        "## Errors",
        *([f"- {e}" for e in errors + close_errors] or ["- none"]),
    ]
    report = "\n".join(lines) + "\n"
    out = HERE / "results" / f"{dataset.stem}-{settings.llm_model}.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text(report)
    print(report)


if __name__ == "__main__":
    main()
