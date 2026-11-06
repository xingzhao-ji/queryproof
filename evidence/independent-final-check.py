"""Final independent capture/results review; does not modify frozen artifacts.

Product APIs validate provenance and reproduce summaries. SQL answers are then
executed separately in fresh in-memory SQLite databases and checked with the
reviewer's pre-gold ordinary-Python reference/comparator, not the product grader.
"""

from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from queryproof import freeze, report, runs  # noqa: E402


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_digest(path):
    return digest(path.read_bytes())


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def main():
    frozen = ROOT / "evidence/frozen-v2"
    raw_path = ROOT / "evidence/model-capture-direct-v1.json"
    run = Path.home() / ".cache/job-apps-runtime/queryproof/runs/direct-v1"
    heldout = run.parent / "independent-heldout-v2"
    manifest = freeze.verify(ROOT, frozen)
    manifest_digest = file_digest(frozen / "manifest.json")
    assert manifest_digest == "585e685d78b28da74ed098ce9988aeaf44aea1c9d00592b38a88d7169ae3dfcb"
    raw = raw_path.read_bytes()
    assert len(raw) == 5442
    assert digest(raw) == "a9a215714428aa6d4fd53c4b0aa92d5423ce7539f0866cea067a6bcce48ff7e1"
    metadata = json.loads((ROOT / "evidence/root-capture-metadata.json").read_text())
    for name, expected_digest in metadata["files"].items():
        assert file_digest(ROOT / name) == expected_digest
    assert metadata["raw_sha256"] == digest(raw)
    assert metadata["raw_bytes"] == len(raw)
    task_text = (ROOT / "evidence/root-capture-task.txt").read_bytes()
    prompt = (frozen / "public-prompt.txt").read_bytes()
    assert task_text.endswith(prompt) and task_text.count(prompt) == 1
    for unknown in ("model_id", "provider_version", "temperature", "token_usage", "generation_cost"):
        assert metadata[unknown] is None
    capture = json.loads(raw)
    state = runs.read(ROOT, run)
    assert (run / "input/raw.json").read_bytes() == raw
    assert state["complete"] and len(state["outcomes"]) == 144
    summary = report.summarize(ROOT, run)
    recorded_summary = json.loads((ROOT / "evidence/model-summary-direct-v1.json").read_text())
    assert summary == recorded_summary
    assert summary["primary_model_denominator"] == 24
    assert summary["primary_model_successes"] == 24
    assert summary["model_by_split"] == {"dev": {"planned": 12, "successes": 12}, "assessment": {"planned": 12, "successes": 12}}
    assert summary["missing_slots"] == summary["invalid_slots"] == 0
    assert summary["label_counts"] == {}
    assert summary["execution_status_counts"] == {"ok": 144}
    assert sum(c["exact"] for c in summary["candidates"]) == 0
    assert sum(c["single"] for c in summary["candidates"]) == 24

    corpus = {name: json.loads((ROOT / f"corpus/{name}.json").read_text())[name]
              for name in ("tasks", "schemas", "worlds")}
    tasks = {t["id"]: t for t in corpus["tasks"]}
    candidates = {c["task_id"]: c for c in capture["candidates"]}
    assert len(capture["candidates"]) == len(candidates) == 24
    assert set(candidates) == set(tasks)
    outcomes = {(o["task_id"], o["world_id"]): o for o in state["outcomes"]}
    expected_artifact = json.loads((ROOT / "evidence/independent-expected.json").read_text())
    expected_by_cell = {(c["task_id"], c["world_id"]): c["expected_rows"] for c in expected_artifact["results"]}
    reference_path = ROOT / "evidence/independent-reference.py"
    assert file_digest(reference_path) == expected_artifact["reference_sha256"]
    spec = importlib.util.spec_from_file_location("independent_reference", reference_path)
    reference = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reference)
    cells = []
    for world in corpus["worlds"]:
        schema = corpus["schemas"][world["schema"]]
        db = sqlite3.connect(":memory:")
        try:
            db.execute("PRAGMA foreign_keys=ON")
            db.executescript(schema["ddl"])
            for table, columns in schema["tables"].items():
                db.executemany(f"INSERT INTO {table} VALUES ({','.join('?' for _ in columns)})",
                               [[row[c] for c in columns] for row in world["tables"][table]])
            assert db.execute("PRAGMA foreign_key_check").fetchall() == []
            db.execute("PRAGMA query_only=ON")
            # These 24 inspected SELECT/CTE queries are finite; retain a bounded
            # reviewer execution guard independently of the product worker.
            steps = [0]
            def progress():
                steps[0] += 1000
                return int(steps[0] > 1000000)
            db.set_progress_handler(progress, 1000)
            for task_id, candidate in candidates.items():
                task = tasks[task_id]
                if task["schema"] != world["schema"]:
                    continue
                steps[0] = 0
                cursor = db.execute(candidate["sql"])
                rows = [list(row) for row in cursor.fetchmany(1001)]
                assert len(rows) <= 1000
                assert len(cursor.description) == len(task["columns"])
                wanted = reference.expected(task_id, world["tables"])
                saved = expected_by_cell[(task_id, world["id"])]
                actual = outcomes[(task_id, world["id"])]["execution"]
                assert reference.independently_equal(task_id, wanted, saved)
                assert reference.independently_equal(task_id, wanted, rows)
                assert reference.independently_equal(task_id, wanted, actual["rows"])
                assert actual["columns"] == len(task["columns"])
                cells.append(dict(task_id=task_id, world_id=world["id"], rows=len(rows),
                                  direct_sql_agrees=True, stored_worker_agrees=True,
                                  direct_rows_sha256=digest(encoded(rows))))
        finally:
            db.close()
    assert len(cells) == 144

    probe_summary = report.summarize(ROOT, heldout)
    assert probe_summary["graders"]["multi"]["false_accepts"] == 1
    assert probe_summary["graders"]["multi"]["evaluated_negatives"] == 6
    assert probe_summary["graders"]["multi"]["false_rejects"] == 0
    negative = next(c for c in probe_summary["candidates"] if c["label"] == "negative" and c["multi"] is False)
    detail = report.inspect(ROOT, heldout, negative["id"])
    witness = detail["counterexample"]
    assert witness and witness["world"]["tables"] and witness["actual"]["status"] == "ok"
    assert not reference.independently_equal(negative["task_id"], witness["expected_rows"], witness["actual"]["rows"])
    assert len(report.compare(ROOT, [run, heldout])["runs"]) == 2
    model_html = (ROOT / "evidence/model-report-direct-v1.html").read_text()
    assert "24 / 24 planned answers passed" in model_html
    assert "144 SQL executions" in model_html
    assert "<script" not in model_html.lower()
    assert model_html.count("<summary>") == 26
    archive_checks = []
    archive = ROOT / "evidence/source-v2.tar.gz"
    with tarfile.open(archive, "r:gz") as bundle:
        names = {m.name.removeprefix("./"): m for m in bundle.getmembers()}
        for name, expected_digest in manifest["files"].items():
            member = names[name]
            assert member.isfile()
            assert digest(bundle.extractfile(member).read()) == expected_digest
            archive_checks.append(name)
    result = dict(
        version=1, status="passed", reviewed_at_utc=datetime.now(timezone.utc).isoformat(),
        method="Fresh independent SQLite execution compared to pre-gold ordinary-Python reference; product read/report APIs used only for artifact verification and report workflow",
        frozen_sha256=manifest_digest, raw_sha256=digest(raw), raw_bytes=len(raw),
        exact_frozen_prompt_suffix=True, captured_candidates=24,
        independent_cells=len(cells), independent_cells_agree=len(cells),
        primary_model_successes=24, primary_model_denominator=24,
        model_by_split=summary["model_by_split"], status_counts=summary["execution_status_counts"],
        exact_string_accepts=0, anchor_accepts=24, multiworld_accepts=24,
        stored_summary_recomputed_equal=True, raw_import_bytes_preserved=True,
        runtime_source_manifest_verified=True, archive_verified_files=len(archive_checks),
        source_archive_sha256=file_digest(archive),
        heldout=dict(false_accepts=1, negatives=6, false_rejects=0, positives=6),
        failure_workflow=dict(candidate_id=negative["id"], world_id=witness["world"]["id"],
                              expected_and_actual_independently_differ=True),
        html=dict(planned_denominator_visible=True, actual_execution_count_visible=True,
                  candidate_disclosures=24, external_scripts=False),
        input_sha256={name:file_digest(ROOT/name) for name in [
            "evidence/model-capture-direct-v1.json", "evidence/root-capture-metadata.json",
            "evidence/root-capture-task.txt", "evidence/model-summary-direct-v1.json",
            "evidence/model-report-direct-v1.html", "evidence/independent-reference.py",
            "evidence/independent-final-check.py"]},
        limitations=[
            "One prompt-only capture; instruction-restricted, not OS-isolated or provider-audited.",
            "Model/version/settings/tokens/cost unavailable; orchestration interval is not inference latency.",
            "24 tasks share known schemas; 144 worlds are not independent model samples.",
            "All real candidates passed; semantic failure diagnosis was demonstrated with separately labeled probes.",
            "LIMIT 100 false accept remains and corpus was not tuned after observing it.",
            "Hash consistency is not publisher authentication or proof of inaccessible hidden context.",
        ], cells=cells)
    destination = ROOT / "evidence/independent-final-review.json"
    with destination.open("x") as output:
        json.dump(result, output, indent=2, sort_keys=True)
        output.write("\n")
    print(json.dumps({k:v for k,v in result.items() if k not in {"cells", "input_sha256", "limitations"}}, indent=2))


if __name__ == "__main__":
    main()
