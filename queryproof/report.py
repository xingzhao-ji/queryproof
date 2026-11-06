"""Calibration and model outcomes retain different denominators."""

from collections import Counter
import html as html_module
import json
from pathlib import Path
from .corpus import load
from .runs import read
from .storage import encoded, read_json, sha


def _metrics(records, grader):
    positives = [r for r in records if r.get("label") == "positive"]
    negatives = [r for r in records if r.get("label") == "negative"]
    pos_done = [r for r in positives if r[grader] is not None]
    neg_done = [r for r in negatives if r[grader] is not None]
    fa = sum(r[grader] is True for r in neg_done)
    fr = sum(r[grader] is False for r in pos_done)
    return dict(
        positive_slots=len(positives),
        negative_slots=len(negatives),
        evaluated_positives=len(pos_done),
        evaluated_negatives=len(neg_done),
        false_accepts=fa,
        false_rejects=fr,
        true_accepts=len(pos_done) - fr,
        true_rejects=len(neg_done) - fa,
        false_accept_rate=fa / len(neg_done) if neg_done else None,
        false_reject_rate=fr / len(pos_done) if pos_done else None,
        pending_slots=len(positives) + len(negatives) - len(pos_done) - len(neg_done),
        negative_execution_rejections=sum(
            r[grader] is False and bool(r["execution_failures"]) for r in neg_done
        )
        if grader != "exact"
        else 0,
    )


def summarize(root, run):
    root = Path(root)
    state = read(root, run)
    corpus = load(root)
    tasks = {t["id"]: t for t in corpus["tasks"]}
    indexed = {(r["candidate_id"], r["world_id"]): r for r in state["outcomes"]}
    records = []
    for candidate in state["candidates"]:
        task = tasks[candidate["task_id"]]
        worlds = [w for w in corpus["worlds"] if w["schema"] == task["schema"]]
        results = [indexed.get((candidate["id"], w["id"])) for w in worlds]
        statuses = Counter(r["execution"]["status"] for r in results if r)
        failures = {k: v for k, v in statuses.items() if k != "ok"}
        records.append(
            dict(
                id=candidate["id"],
                task_id=task["id"],
                category=task["category"],
                split=task["split"],
                label=candidate.get("label"),
                label_kind=candidate.get("label_kind"),
                capture_error=candidate["capture_error"],
                completed_worlds=sum(r is not None for r in results),
                planned_worlds=len(worlds),
                execution_failures=failures,
                exact=isinstance(candidate["sql"], str)
                and candidate["sql"].strip() == corpus["oracles"][task["id"]].strip(),
                single=results[0]["comparison"]["pass"] if results[0] else None,
                multi=all(r["comparison"]["pass"] for r in results)
                if all(results)
                else None,
            )
        )
    graders = {g: _metrics(records, g) for g in ("exact", "single", "multi")}
    grouped = {
        field: {
            value: {
                g: _metrics([r for r in records if r[field] == value], g)
                for g in graders
            }
            for value in sorted({r[field] for r in records})
        }
        for field in ("task_id", "category", "split")
    }
    is_model = state["manifest"]["kind"] == "agent_capture"
    successes = sum(r["multi"] is True for r in records)
    missing = sum(r["capture_error"] == "missing" for r in records)
    invalid = sum(
        r["capture_error"] in {"invalid_sql", "invalid_capture"} for r in records
    )
    return dict(
        version=1,
        title="QueryProof evaluation",
        run_sha256=state["run_sha256"],
        frozen_sha256=state["manifest"]["frozen_sha256"],
        kind=state["manifest"]["kind"],
        cohort=state["manifest"]["cohort"],
        execution_complete=state["complete"],
        capture_complete=missing == 0 and invalid == 0,
        capture_failure=state["canonical"]["capture_failure"],
        capture_failure_detail=state["canonical"]["capture_failure_detail"],
        planned_slots=state["planned_slots"],
        captured_slots=len(state["canonical"]["candidates"]),
        planned_worlds=state["planned_worlds"],
        completed_worlds=state["completed_worlds"],
        executed_worlds=sum(
            o["execution"]["status"]
            not in {"missing", "invalid_sql", "invalid_capture"}
            for o in state["outcomes"]
        ),
        execution_status_counts=dict(
            Counter(o["execution"]["status"] for o in state["outcomes"])
        ),
        missing_slots=missing,
        invalid_slots=invalid,
        executable_slots=len(records) - missing - invalid,
        primary_model_denominator=len(records) if is_model else None,
        primary_model_successes=successes if is_model else None,
        primary_model_success_rate=successes / len(records)
        if is_model and records
        else None,
        model_by_split={
            split: dict(
                planned=sum(r["split"] == split for r in records),
                successes=sum(
                    r["split"] == split and r["multi"] is True for r in records
                ),
            )
            for split in ("dev", "assessment")
        }
        if is_model
        else None,
        label_counts=dict(Counter(r["label"] for r in records if r["label"])),
        gold_sanity=dict(
            planned=sum(r["label"] == "sanity" for r in records),
            multi_passed=sum(
                r["label"] == "sanity" and r["multi"] is True for r in records
            ),
        ),
        graders=graders,
        by=grouped,
        candidates=records,
        limitations=[
            "Finite authored worlds do not prove universal SQL equivalence or benchmark generalization.",
            "Gold identity sanity, labeled equivalents/mutants, policy probes and real captures have separate denominators.",
            "Labels are agent-authored/reviewed claims; no human label agreement or authenticated provenance is claimed.",
            "Worlds are not independent model samples; assessment tasks share known schemas.",
            "Hash integrity is not publisher authentication. Hosted generation is not claimed reproducible.",
            "Execution failures are non-acceptances; negative execution rejections are separately counted, not semantic counterexample credit.",
        ],
    )


def inspect(root, run, candidate_id):
    root = Path(root)
    state = read(root, run)
    corpus = load(root)
    candidate = next((c for c in state["candidates"] if c["id"] == candidate_id), None)
    if candidate is None:
        raise ValueError("unknown candidate")
    task = next(t for t in corpus["tasks"] if t["id"] == candidate["task_id"])
    expected = {
        (r["task_id"], r["world_id"]): r["expected_rows"]
        for r in read_json(root / "evidence/independent-expected.json")["results"]
    }
    indexed = {(r["candidate_id"], r["world_id"]): r for r in state["outcomes"]}
    detail = dict(
        candidate=candidate,
        task=task,
        sql=candidate["sql"],
        counterexample=None,
        coverage=[],
    )
    for world in (w for w in corpus["worlds"] if w["schema"] == task["schema"]):
        result = indexed.get((candidate_id, world["id"]))
        detail["coverage"].append(
            dict(
                world_id=world["id"],
                pass_=result["comparison"]["pass"] if result else None,
                status=result["execution"]["status"] if result else "pending",
            )
        )
        if (
            result
            and not result["comparison"]["pass"]
            and detail["counterexample"] is None
        ):
            detail["counterexample"] = dict(
                world=world,
                world_sha256=sha(encoded(world)),
                database_sha256=state["manifest"]["files"][
                    "worlds/" + world["id"] + ".db"
                ],
                expected_rows=expected[(task["id"], world["id"])],
                actual=result["execution"],
                reason=result["comparison"]["reason"],
            )
    return detail


def compare(root, paths):
    summaries = [summarize(root, p) for p in paths]
    if len({s["frozen_sha256"] for s in summaries}) != 1:
        raise ValueError("compare requires the same frozen suite and implementation")
    return dict(
        version=1,
        runs=summaries,
        interpretation="Within each run exact/single/multi grade the same candidates. Different cohorts are not independent models unless separately established.",
    )


def html(summary, diagnostics):
    escape = html_module.escape

    def block(value):
        return (
            "<pre>"
            + escape(json.dumps(value, indent=2, ensure_ascii=True, allow_nan=False))
            + "</pre>"
        )

    metrics = summary.get("graders", {})
    rows = "".join(
        "<tr><th>"
        + escape(g)
        + "</th><td>"
        + str(m["false_accepts"])
        + " / "
        + str(m["evaluated_negatives"])
        + "</td><td>"
        + str(m["false_rejects"])
        + " / "
        + str(m["evaluated_positives"])
        + "</td><td>"
        + str(m["pending_slots"])
        + "</td></tr>"
        for g, m in metrics.items()
    )
    if summary.get("kind") == "agent_capture":
        headline = (
            "<h2>"
            + str(summary["primary_model_successes"])
            + " / "
            + str(summary["primary_model_denominator"])
            + " planned answers passed</h2>"
        )
        headline += (
            "<p>"
            + str(summary["completed_worlds"])
            + " / "
            + str(summary["planned_worlds"])
            + " world outcomes recorded; "
            + str(summary["executed_worlds"])
            + " SQL executions. "
            + str(summary["missing_slots"])
            + " missing; "
            + str(summary["invalid_slots"])
            + " invalid answers.</p>"
        )
        if summary.get("capture_failure"):
            headline += (
                "<p><strong>Capture failed:</strong> "
                + escape(summary["capture_failure"])
                + ". All planned slots remain in the denominator.</p>"
            )
        headline += (
            "<table><caption>Known-schema task split</caption><tr><th>Split</th><th>Successes / planned</th></tr>"
            + "".join(
                "<tr><th>"
                + escape(name)
                + "</th><td>"
                + str(value["successes"])
                + " / "
                + str(value["planned"])
                + "</td></tr>"
                for name, value in summary["model_by_split"].items()
            )
            + "</table>"
        )
    elif summary.get("kind") == "safety_probe":
        headline = (
            "<h2>Safety probes: "
            + str(summary["planned_slots"])
            + " planned queries</h2><p>Execution policy outcomes are excluded from semantic false-accept/reject rates.</p>"
            + block(summary["execution_status_counts"])
        )
    else:
        headline = (
            "<table><caption>Grader calibration — labeled equivalents and semantic mutants only</caption><thead><tr><th>Grader</th><th>False accepts / negatives</th><th>False rejects / positives</th><th>Pending</th></tr></thead><tbody>"
            + rows
            + "</tbody></table>"
        )
    cards = []
    for detail in diagnostics:
        candidate = detail.get("candidate", {})
        title = (
            candidate.get("id", "Candidate")
            + " · "
            + detail.get("task", {}).get("category", "")
        )
        failure = detail.get("counterexample")
        cards.append(
            "<details><summary>"
            + escape(title)
            + (" — counterexample" if failure else " — no recorded mismatch")
            + "</summary><p>"
            + escape(detail.get("task", {}).get("prompt", ""))
            + "</p><p>Imported label: "
            + escape(str(candidate.get("label", "unlabeled")))
            + ". "
            + escape(candidate.get("rationale", ""))
            + "</p><h3>SQL</h3>"
            + block(detail.get("sql"))
            + "<h3>Coverage and diagnostic</h3>"
            + block(
                {
                    k: v
                    for k, v in detail.items()
                    if k not in {"sql", "candidate", "task"}
                }
            )
            + "</details>"
        )
    overview = {
        k: v for k, v in summary.items() if k not in {"candidates", "by", "graders"}
    }
    return (
        """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'"><title>QueryProof report</title><style>body{font:16px system-ui,sans-serif;line-height:1.5;max-width:1120px;margin:48px auto;padding:0 24px;color:#18302c;background:#f7f8f5}h1{font-size:44px;margin-bottom:8px}p{max-width:85ch}table{width:100%;border-collapse:collapse;background:white}th,td{text-align:left;padding:12px;border-bottom:1px solid #d0d9d3}details{margin:16px 0;border:1px solid #c1cec8;background:white;padding:18px;border-radius:8px}summary{cursor:pointer;font-weight:650}pre{overflow:auto;max-height:600px;font:13px ui-monospace,monospace;white-space:pre-wrap;overflow-wrap:anywhere;background:#edf2ee;padding:16px}small{color:#48675d}</style><h1>QueryProof</h1><p>Inspect what a SQL answer does across multiple database worlds. A finite passing suite is evidence, not proof of universal equivalence.</p>"""
        + headline
        + "<details><summary>Provenance, coverage and limits</summary>"
        + block(overview)
        + "</details><h2>Candidate diagnosis</h2><p>Open a candidate to see its SQL, the first failing world, full small-world rows, expected result and actual execution.</p>"
        + "".join(cards)
        + "<details><summary>Task/category/split breakdown</summary>"
        + block(summary.get("by", {}))
        + "</details><small>Local standalone artifact. No remote scripts, fonts, telemetry or services.</small></html>"
    )
