"""Independent SQL-vs-Python and authored-control adjudication, after both freezes."""
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


REASONS = {
    "C01": "Every customer survives even without matching line rows; correlated paid-line aggregation is equivalent. The mutant removes no-line customers.",
    "C02": "A non-null order primary key makes the anti-join equivalent. The mutant also forbids non-paid orders.",
    "C03": "Both valid forms count orders directly. Joining lines changes the counted unit and omits zero-line orders.",
    "C04": "Date then ID defines a total order. Anti-dominance selects its unique maximum; maximum ID alone is insufficient.",
    "C05": "Line membership preserves multiplicity and the half-open date interval. Including the February boundary is incorrect.",
    "C06": "Correlated totals and joined totals rank the same customers; descending ID breaks the required tie direction.",
    "C07": "Membership and the PK join preserve one output per line. DISTINCT discards required repetitions.",
    "C08": "Existence of each of A and B is equivalent to two distinct matching SKUs. Either-SKU membership is weaker.",
    "S01": "Counting matching ticket IDs or a correlated count yields zero for empty agents; the inner join omits them.",
    "S02": "The anti-join checks ticket ID after correlation and ignores null assignments. NOT IN over nullable agent IDs can exclude all rows.",
    "S03": "Both valid forms count reply records per ticket. Including notes changes the count and qualifying set.",
    "S04": "Anti-dominance implements earliest date then least ID. The reversed ID tie choice violates the contract.",
    "S05": "For null resolution the high sentinel qualifies, matching the explicit null branch; currently unresolved-only wrongly drops later-resolved tickets.",
    "S06": "Unique priority/ID ordering makes the first three row numbers equivalent to LIMIT. Reversing IDs changes ties.",
    "S07": "Grouping team names after the join returns each qualifying team once. Per-agent emission duplicates shared teams.",
    "S08": "The two existence conditions equal two positive conditional counts. Priority 1 must not satisfy the low-priority condition.",
    "B01": "One payment sum per invoice is equivalent to grouped joins. Inner joining payments loses unpaid invoices.",
    "B02": "Aggregate signed invoice balances before account filtering. Removing negative balances changes overpayment offsets.",
    "B03": "Both anti-joins ask whether any payment row exists. Positive remaining debt is a different condition.",
    "B04": "A nonempty group with maximum balance <=0 has every invoice non-positive. Omitting existence admits no-invoice accounts.",
    "B05": "Distinct months plus a correlated invoice sum equal grouped billing totals. Payment totals measure something else.",
    "B06": "The correlated prefix includes payments through the current date/ID pair. RANGE over date alone absorbs same-date peers too early.",
    "B07": "Floating sum divided by invoice count gives equal invoice weights. Averaging account means changes weights when counts differ.",
    "B08": "The January-filtered anti-join preserves active accounts with only other-month invoices. Rejecting any invoice is stronger than requested.",
}


def main():
    spec = importlib.util.spec_from_file_location("independent_reference", ROOT / "evidence/independent-reference.py")
    reference = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reference)
    expected = json.loads((ROOT / "evidence/independent-expected.json").read_text())
    for relative, digest in expected["input_sha256"].items():
        assert sha(ROOT / relative) == digest, f"Input changed: {relative}"
    assert sha(ROOT / "evidence/independent-reference.py") == expected["reference_sha256"]
    owner = json.loads((ROOT / "evidence/owner-gold-authored.json").read_text())
    for relative, digest in owner["sha256"].items():
        assert sha(ROOT / relative) == digest, f"Authored SQL changed: {relative}"
    lookup = {(r["task_id"], r["world_id"]): r["expected_rows"] for r in expected["results"]}
    corpus = {name: json.loads((ROOT / f"corpus/{name}.json").read_text())[name]
              for name in ("tasks", "schemas", "worlds", "oracles", "controls")}
    tasks = {t["id"]: t for t in corpus["tasks"]}
    cells, control_cells = [], []
    for world in corpus["worlds"]:
        schema = corpus["schemas"][world["schema"]]
        with sqlite3.connect(":memory:") as db:
            db.execute("PRAGMA foreign_keys=ON")
            db.executescript(schema["ddl"])
            for table, columns in schema["tables"].items():
                sql = f"INSERT INTO {table} VALUES ({','.join('?' for _ in columns)})"
                db.executemany(sql, [[r[c] for c in columns] for r in world["tables"][table]])
            assert db.execute("PRAGMA foreign_key_check").fetchall() == []
            db.execute("PRAGMA query_only=ON")
            for task in tasks.values():
                if task["schema"] != world["schema"]:
                    continue
                observed = [list(row) for row in db.execute(corpus["oracles"][task["id"]])]
                wanted = lookup[(task["id"], world["id"])]
                cells.append({"task_id": task["id"], "world_id": world["id"],
                              "match": reference.independently_equal(task["id"], wanted, observed),
                              "expected_rows": wanted, "observed_rows": observed})
            for control in corpus["controls"]:
                task = tasks[control["task_id"]]
                if task["schema"] != world["schema"]:
                    continue
                observed = [list(row) for row in db.execute(control["sql"])]
                wanted = lookup[(task["id"], world["id"])]
                control_cells.append({"candidate_id": control["id"], "task_id": task["id"],
                                      "world_id": world["id"], "world_role": world["role"],
                                      "match": reference.independently_equal(task["id"], wanted, observed),
                                      "expected_rows": wanted, "observed_rows": observed})
    adjudicated = []
    for control in corpus["controls"]:
        records = [r for r in control_cells if r["candidate_id"] == control["id"]]
        assert len(records) == 6
        all_match = all(r["match"] for r in records)
        anchor = next(r["match"] for r in records if r["world_role"] == "anchor")
        correct_label = all_match if control["label"] in {"positive", "sanity"} else not all_match
        adjudicated.append({"candidate_id": control["id"], "task_id": control["task_id"],
                            "label": control["label"], "label_kind": control["label_kind"],
                            "label_supported": correct_label, "anchor_accepts": anchor,
                            "suite_accepts": all_match, "reviewer_reason": REASONS[control["task_id"]],
                            "first_counterexample": next((r for r in records if not r["match"]), None)})
    common = {"version": 1, "recorded_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "method": "Direct SQLite execution of inspected authored SQL against independently frozen Python answers; independent typed comparison, no product executor/grader imports.",
              "input_sha256": dict(expected["input_sha256"], **{
                  "corpus/oracles.json": sha(ROOT / "corpus/oracles.json"),
                  "evidence/independent-expected.json": sha(ROOT / "evidence/independent-expected.json")}),
              "reference_sha256": expected["reference_sha256"],
              "expected_file_sha256": sha(ROOT / "evidence/independent-expected.json"),
              "sql_sha256": owner["sha256"], "checker_sha256": sha(Path(__file__)),
              "python_sqlite_version": sqlite3.sqlite_version,
              "scope": "Synthetic authored controls; not real model outputs, human labels or universal SQL-equivalence proof."}
    oracle_report = dict(common, status="passed" if all(r["match"] for r in cells) else "failed",
                         cells=len(cells), compared_cells=len(cells), matched_cells=sum(r["match"] for r in cells), comparisons=cells)
    label_report = dict(common, status="passed" if all(r["label_supported"] for r in adjudicated) else "failed",
                        candidate_count=len(adjudicated), execution_cells=len(control_cells), adjudications=adjudicated)
    for name, data in [("independent-oracle-review.json", oracle_report),
                       ("independent-control-adjudication.json", label_report)]:
        (ROOT / "evidence" / name).write_text(json.dumps(data, indent=2) + "\n")
    negatives = [r for r in adjudicated if r["label"] == "negative"]
    print(json.dumps({"oracle_status": oracle_report["status"], "matched_cells": oracle_report["matched_cells"],
                      "label_status": label_report["status"], "labels": len(adjudicated),
                      "equivalent_false_rejects": sum(not r["suite_accepts"] for r in adjudicated if r["label"] == "positive"),
                      "mutant_anchor_false_accepts": sum(r["anchor_accepts"] for r in negatives),
                      "mutant_suite_false_accepts": sum(r["suite_accepts"] for r in negatives),
                      "unsupported_labels": [r["candidate_id"] for r in adjudicated if not r["label_supported"]]}, indent=2))


if __name__ == "__main__":
    main()
