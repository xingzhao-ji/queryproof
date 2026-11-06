"""Read-only independent corpus audit and expected-result export; no SQL used."""

import datetime
import hashlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REF_PATH = ROOT / "evidence/independent-reference.py"
spec = importlib.util.spec_from_file_location("independent_reference", REF_PATH)
reference = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reference)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def date(value):
    assert type(value) is str
    assert datetime.date.fromisoformat(value).isoformat() == value


def integer(value, lo, hi=None):
    assert type(value) is int and value >= lo
    assert hi is None or value <= hi


def validate(schema, tables):
    ids = {}
    for name, rows in tables.items():
        ids[name] = set()
        for row in rows:
            integer(row["id"], 1)
            assert row["id"] not in ids[name]
            ids[name].add(row["id"])
    if schema == "commerce":
        for row in tables["customers"]:
            assert row["region"] is None or type(row["region"]) is str
        for row in tables["orders"]:
            assert row["customer_id"] in ids["customers"]
            assert row["status"] in {"paid", "pending", "cancelled"}
            date(row["ordered_on"])
        for row in tables["lines"]:
            assert row["order_id"] in ids["orders"]
            assert row["sku"] in {"A", "B", "C"}
            integer(row["quantity"], 1, 5)
            integer(row["unit_cents"], 0, 10000)
    elif schema == "support":
        for row in tables["agents"]:
            assert type(row["team"]) is str
        tickets = {row["id"]: row for row in tables["tickets"]}
        for row in tables["tickets"]:
            assert row["agent_id"] is None or row["agent_id"] in ids["agents"]
            date(row["opened_on"])
            integer(row["priority"], 0, 3)
            if row["resolved_on"] is not None:
                date(row["resolved_on"])
                assert row["resolved_on"] >= row["opened_on"]
        for row in tables["events"]:
            assert row["ticket_id"] in ids["tickets"]
            assert row["kind"] in {"reply", "note"}
            date(row["happened_on"])
            assert row["happened_on"] >= tickets[row["ticket_id"]]["opened_on"]
    elif schema == "billing":
        invoices = {row["id"]: row for row in tables["invoices"]}
        for row in tables["accounts"]:
            assert row["plan"] in {"basic", "pro"}
            integer(row["active"], 0, 1)
        for row in tables["invoices"]:
            assert row["account_id"] in ids["accounts"]
            date(row["issued_on"])
            integer(row["total_cents"], 0, 50000)
        for row in tables["payments"]:
            assert row["invoice_id"] in ids["invoices"]
            integer(row["amount_cents"], 1, 50000)
            date(row["paid_on"])
            assert row["paid_on"] >= invoices[row["invoice_id"]]["issued_on"]
    else:
        raise AssertionError(schema)


def main():
    tasks = json.loads((ROOT / "corpus/tasks.json").read_text())["tasks"]
    worlds = json.loads((ROOT / "corpus/worlds.json").read_text())["worlds"]
    schemas = json.loads((ROOT / "corpus/schemas.json").read_text())["schemas"]
    assert len(tasks) == len({task["id"] for task in tasks}) == 24
    assert len(worlds) == len({world["id"] for world in worlds}) == 18
    contract = {}
    for line in (ROOT / "docs/task-contract.md").read_text().splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) == 5 and cells[0] in {task["id"] for task in tasks}:
            contract[cells[0]] = cells
    assert len(contract) == 24
    for task in tasks:
        row = contract[task["id"]]
        assert [task["id"], task["split"], task["category"], task["prompt"], task["semantics"]] == row
        assert task["ordered"] == (task["id"] in reference.ORDERED)
    results = []
    for world in worlds:
        schema = schemas[world["schema"]]
        assert set(world["tables"]) == set(schema["tables"])
        for table, rows in world["tables"].items():
            for row in rows:
                assert set(row) == set(schema["tables"][table])
        validate(world["schema"], world["tables"])
        for task in tasks:
            if task["schema"] == world["schema"]:
                rows = reference.expected(task["id"], world["tables"])
                assert reference.independently_equal(task["id"], rows, rows)
                for row in rows:
                    assert len(row) == len(task["columns"])
                results.append({"task_id": task["id"], "world_id": world["id"], "expected_rows": rows})
    assert len(results) == 144
    assert sum(task["split"] == "assessment" for task in tasks) == 12
    result = {
        "version": 1,
        "recorded_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "method": "Independent ordinary-Python arithmetic, sets, iteration and sorting from task contracts; no SQL or project implementation imports.",
        "reference_sha256": sha(REF_PATH),
        "audit_script_sha256": sha(Path(__file__)),
        "input_sha256": {str(p.relative_to(ROOT)): sha(p) for p in [
            ROOT / "corpus/tasks.json", ROOT / "corpus/schemas.json", ROOT / "corpus/worlds.json",
            ROOT / "docs/task-contract.md"]},
        "gold_file_present_at_export": (ROOT / "corpus/oracles.json").exists(),
        "gold_or_production_grader_inspected": False,
        "validated_worlds": len(worlds),
        "validated_task_contracts": len(tasks),
        "expected_cells": len(results),
        "comparison_status": "pending_gold_sql_execution",
        "world_policy_observed": "Per schema: one anchor, one edge, three seeded generated worlds and one all-empty world.",
        "results": results,
    }
    output = ROOT / "evidence/independent-expected.json"
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"path": str(output), "sha256": sha(output), "cells": len(results),
                      "worlds": len(worlds), "comparison_status": result["comparison_status"]}, indent=2))


if __name__ == "__main__":
    main()
