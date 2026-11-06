"""Reviewer reference derived from task-contract.md before viewing gold SQL.

This is a review artifact, not the product oracle. No QueryProof imports, SQLite,
SQL parsing, or production grading code are used. Input tables contain row dicts.
"""

from collections import Counter
from fractions import Fraction
from math import isclose, isfinite


ORDERED = {"C06", "S06", "B05", "B06"}


def expected(task_id, tables):
    """Compute the task's specified rows using ordinary Python data operations."""
    if task_id.startswith("C"):
        customers = tables["customers"]
        orders = tables["orders"]
        lines = tables["lines"]
        paid = {o["id"]: o for o in orders if o["status"] == "paid"}
        revenue = {c["id"]: 0 for c in customers}
        bought = {c["id"]: set() for c in customers}
        for line in lines:
            order = paid.get(line["order_id"])
            if order is not None:
                owner = order["customer_id"]
                revenue[owner] += line["quantity"] * line["unit_cents"]
                bought[owner].add(line["sku"])

        if task_id == "C01":
            return [[c["id"], revenue[c["id"]]] for c in customers]
        if task_id == "C02":
            owners = {o["customer_id"] for o in paid.values()}
            return [[c["id"]] for c in customers if c["id"] not in owners]
        if task_id == "C03":
            counts = Counter(o["customer_id"] for o in paid.values())
            return [[owner, count] for owner, count in counts.items() if count >= 2]
        if task_id == "C04":
            latest = {}
            for order in paid.values():
                owner = order["customer_id"]
                rank = (order["ordered_on"], order["id"])
                if owner not in latest or rank > latest[owner]:
                    latest[owner] = rank
            return [[owner, rank[1]] for owner, rank in latest.items()]
        if task_id == "C05":
            total = 0
            for line in lines:
                order = paid.get(line["order_id"])
                if order and "2025-01-01" <= order["ordered_on"] < "2025-02-01":
                    total += line["quantity"] * line["unit_cents"]
            return [[total]]
        if task_id == "C06":
            ranked = sorted(revenue, key=lambda owner: (-revenue[owner], owner))
            return [[owner, revenue[owner]] for owner in ranked[:2]]
        if task_id == "C07":
            return [[line["sku"]] for line in lines if line["order_id"] in paid]
        if task_id == "C08":
            return [[owner] for owner, skus in bought.items() if {"A", "B"} <= skus]

    elif task_id.startswith("S"):
        agents = tables["agents"]
        tickets = tables["tickets"]
        events = tables["events"]
        if task_id == "S01":
            counts = Counter(t["agent_id"] for t in tickets if t["agent_id"] is not None)
            return [[a["id"], counts[a["id"]]] for a in agents]
        if task_id == "S02":
            blocked = {t["agent_id"] for t in tickets if t["resolved_on"] is None}
            return [[a["id"]] for a in agents if a["id"] not in blocked]
        if task_id == "S03":
            replies = Counter(e["ticket_id"] for e in events if e["kind"] == "reply")
            return [[ticket, count] for ticket, count in replies.items() if count >= 2]
        if task_id == "S04":
            earliest = {}
            for event in events:
                if event["kind"] != "reply":
                    continue
                ticket = event["ticket_id"]
                rank = (event["happened_on"], event["id"])
                if ticket not in earliest or rank < earliest[ticket]:
                    earliest[ticket] = rank
            return [[ticket, rank[1]] for ticket, rank in earliest.items()]
        if task_id == "S05":
            return [[t["id"]] for t in tickets
                    if "2025-01-01" <= t["opened_on"] < "2025-02-01"
                    and (t["resolved_on"] is None or t["resolved_on"] >= "2025-02-01")]
        if task_id == "S06":
            unresolved = [t for t in tickets if t["resolved_on"] is None]
            unresolved.sort(key=lambda t: (-t["priority"], t["id"]))
            return [[t["id"], t["priority"]] for t in unresolved[:3]]
        if task_id == "S07":
            assigned = {t["agent_id"] for t in tickets if t["agent_id"] is not None}
            return [[team] for team in sorted({a["team"] for a in agents if a["id"] in assigned})]
        if task_id == "S08":
            high = {t["agent_id"] for t in tickets if t["priority"] >= 2}
            low = {t["agent_id"] for t in tickets if t["priority"] == 0}
            return [[a["id"]] for a in agents if a["id"] in high and a["id"] in low]

    elif task_id.startswith("B"):
        accounts = tables["accounts"]
        invoices = tables["invoices"]
        payments = tables["payments"]
        paid = Counter()
        for payment in payments:
            paid[payment["invoice_id"]] += payment["amount_cents"]
        outstanding = {i["id"]: i["total_cents"] - paid[i["id"]] for i in invoices}
        if task_id == "B01":
            return [[i["id"], outstanding[i["id"]]] for i in invoices]
        if task_id == "B02":
            by_account = Counter()
            for invoice in invoices:
                by_account[invoice["account_id"]] += outstanding[invoice["id"]]
            return [[account, amount] for account, amount in by_account.items() if amount > 0]
        if task_id == "B03":
            any_payment = {p["invoice_id"] for p in payments}
            return [[i["id"]] for i in invoices if i["id"] not in any_payment]
        if task_id == "B04":
            present = {i["account_id"] for i in invoices}
            still_due = {i["account_id"] for i in invoices if outstanding[i["id"]] > 0}
            return [[a["id"]] for a in accounts if a["id"] in present and a["id"] not in still_due]
        if task_id == "B05":
            by_month = Counter()
            for invoice in invoices:
                by_month[invoice["issued_on"][:7]] += invoice["total_cents"]
            return [[month, by_month[month]] for month in sorted(by_month)]
        if task_id == "B06":
            ordered = sorted(payments, key=lambda p: (p["invoice_id"], p["paid_on"], p["id"]))
            cumulative = Counter()
            rows = []
            for payment in ordered:
                invoice = payment["invoice_id"]
                cumulative[invoice] += payment["amount_cents"]
                rows.append([invoice, payment["id"], cumulative[invoice]])
            return rows
        if task_id == "B07":
            plan_for = {a["id"]: a["plan"] for a in accounts}
            totals, counts = Counter(), Counter()
            for invoice in invoices:
                plan = plan_for[invoice["account_id"]]
                totals[plan] += invoice["total_cents"]
                counts[plan] += 1
            return [[plan, float(Fraction(totals[plan], counts[plan]))] for plan in sorted(counts)]
        if task_id == "B08":
            january = {i["account_id"] for i in invoices
                       if "2025-01-01" <= i["issued_on"] < "2025-02-01"}
            return [[a["id"]] for a in accounts if a["active"] == 1 and a["id"] not in january]
    raise ValueError(f"Unsupported task ID: {task_id}")


def independently_equal(task_id, wanted, actual):
    """Separate reviewer comparison; no production comparator is called."""
    if not isinstance(actual, list) or len(actual) != len(wanted):
        return False
    if any(not isinstance(row, (list, tuple)) for row in actual):
        return False
    if task_id == "B07":
        # Contract guarantees exactly one result per represented plan.
        got = {}
        for row in actual:
            if len(row) != 2 or type(row[0]) is not str or row[0] in got:
                return False
            if type(row[1]) not in (int, float) or not isfinite(row[1]):
                return False
            got[row[0]] = row[1]
        return all(plan in got and isclose(value, got[plan], rel_tol=1e-9, abs_tol=1e-9)
                   for plan, value in wanted)
    normalized = []
    for row in actual:
        reference_width = len(wanted[0]) if wanted else 0
        if len(row) != reference_width:
            return False
        # Every other task column is an integer except C07/S07 and B05's month.
        types = [str] if task_id in {"C07", "S07"} else ([str, int] if task_id == "B05" else [int] * len(row))
        if any(type(cell) is not typ for cell, typ in zip(row, types)):
            return False
        normalized.append(tuple(row))
    wanted_rows = [tuple(row) for row in wanted]
    if task_id in ORDERED:
        return normalized == wanted_rows
    return Counter(normalized) == Counter(wanted_rows)


def _self_check():
    # Independent hand-reasoned fixtures: empty inputs and selected edge cases.
    empty = {name: [] for name in (
        "customers", "orders", "lines", "agents", "tickets", "events",
        "accounts", "invoices", "payments")}
    for prefix in "CSB":
        for number in range(1, 9):
            task = f"{prefix}{number:02}"
            assert expected(task, empty) == ([[0]] if task == "C05" else [])

    commerce = {
        "customers": [{"id": 1, "region": None}, {"id": 2, "region": "x"}, {"id": 3, "region": "x"}],
        "orders": [
            {"id": 1, "customer_id": 1, "status": "paid", "ordered_on": "2025-01-01"},
            {"id": 2, "customer_id": 1, "status": "paid", "ordered_on": "2025-01-01"},
            {"id": 3, "customer_id": 2, "status": "pending", "ordered_on": "2025-02-01"}],
        "lines": [
            {"id": 1, "order_id": 1, "sku": "A", "quantity": 2, "unit_cents": 7},
            {"id": 2, "order_id": 1, "sku": "A", "quantity": 1, "unit_cents": 0},
            {"id": 3, "order_id": 2, "sku": "B", "quantity": 1, "unit_cents": 0}]}
    cases = {"C01": [[1, 14], [2, 0], [3, 0]], "C02": [[2], [3]], "C03": [[1, 2]],
             "C04": [[1, 2]], "C05": [[14]], "C06": [[1, 14], [2, 0]],
             "C07": [["A"], ["A"], ["B"]], "C08": [[1]]}
    for task, rows in cases.items():
        assert independently_equal(task, rows, expected(task, commerce)), task

    support = {
        "agents": [{"id": 1, "team": "same"}, {"id": 2, "team": "same"}, {"id": 3, "team": "other"}],
        "tickets": [
            {"id": 1, "agent_id": 1, "opened_on": "2025-01-01", "resolved_on": "2025-02-01", "priority": 2},
            {"id": 2, "agent_id": 1, "opened_on": "2024-12-31", "resolved_on": None, "priority": 0},
            {"id": 3, "agent_id": None, "opened_on": "2025-01-31", "resolved_on": None, "priority": 3},
            {"id": 4, "agent_id": 2, "opened_on": "2025-02-01", "resolved_on": "2025-02-01", "priority": 1}],
        "events": [
            {"id": 2, "ticket_id": 1, "kind": "reply", "happened_on": "2025-01-02"},
            {"id": 1, "ticket_id": 1, "kind": "reply", "happened_on": "2025-01-02"},
            {"id": 3, "ticket_id": 2, "kind": "note", "happened_on": "2025-01-02"}]}
    cases = {"S01": [[1, 2], [2, 1], [3, 0]], "S02": [[2], [3]], "S03": [[1, 2]],
             "S04": [[1, 1]], "S05": [[1], [3]], "S06": [[3, 3], [2, 0]],
             "S07": [["same"]], "S08": [[1]]}
    for task, rows in cases.items():
        assert independently_equal(task, rows, expected(task, support)), task

    billing = {
        "accounts": [{"id": 1, "plan": "basic", "active": 1}, {"id": 2, "plan": "basic", "active": 1},
                     {"id": 3, "plan": "pro", "active": 1}, {"id": 4, "plan": "pro", "active": 0}],
        "invoices": [
            {"id": 1, "account_id": 1, "issued_on": "2025-01-01", "total_cents": 10},
            {"id": 2, "account_id": 1, "issued_on": "2025-02-01", "total_cents": 20},
            {"id": 3, "account_id": 2, "issued_on": "2025-01-31", "total_cents": 0}],
        "payments": [
            {"id": 2, "invoice_id": 1, "amount_cents": 12, "paid_on": "2025-01-02"},
            {"id": 1, "invoice_id": 1, "amount_cents": 3, "paid_on": "2025-01-02"}]}
    cases = {"B01": [[1, -5], [2, 20], [3, 0]], "B02": [[1, 15]], "B03": [[2], [3]],
             "B04": [[2]], "B05": [["2025-01", 10], ["2025-02", 20]],
             "B06": [[1, 1, 3], [1, 2, 15]], "B07": [["basic", 10.0]], "B08": [[3]]}
    for task, rows in cases.items():
        assert independently_equal(task, rows, expected(task, billing)), task
    assert not independently_equal("C07", [["A"], ["A"]], [["A"]])
    assert not independently_equal("C01", [[1, 2]], [[True, 2]])
    assert not independently_equal("C01", [[1, 2]], [[1, 2.0]])
    assert not independently_equal("B07", [["basic", 10.0]], [["basic", float("nan")]])
    print("Independent reference self-checks passed: 24 empty cases, 24 hand-reasoned cases, 4 comparator negatives.")


if __name__ == "__main__":
    _self_check()
