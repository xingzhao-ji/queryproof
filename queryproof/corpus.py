"""Versioned synthetic fixtures; no data from applications or real customers."""

from datetime import date
from contextlib import closing
import json
from pathlib import Path
import random
import sqlite3


def records(columns, rows):
    return [dict(zip(columns.split(), row, strict=True)) for row in rows]


def edge(schema):
    if schema == "commerce":
        return {
            "customers": records(
                "id region",
                [
                    (1, "north"),
                    (2, "south"),
                    (3, None),
                    (4, "north"),
                    (5, "west"),
                    (6, "south"),
                    (7, "east"),
                ],
            ),
            "orders": records(
                "id customer_id status ordered_on",
                [
                    (1, 1, "paid", "2025-01-01"),
                    (2, 1, "paid", "2025-01-15"),
                    (3, 2, "pending", "2025-01-15"),
                    (4, 3, "paid", "2025-02-01"),
                    (5, 2, "paid", "2024-12-31"),
                    (6, 2, "paid", "2025-01-31"),
                    (7, 3, "paid", "2025-01-15"),
                    (8, 4, "cancelled", "2025-01-15"),
                    (9, 1, "paid", "2025-01-15"),
                    (10, 5, "paid", "2025-01-31"),
                    (11, 6, "paid", "2025-01-15"),
                    (12, 5, "paid", "2025-01-16"),
                ],
            ),
            "lines": records(
                "id order_id sku quantity unit_cents",
                [
                    (1, 1, "A", 1, 100),
                    (2, 1, "A", 2, 100),
                    (3, 2, "B", 1, 300),
                    (4, 9, "C", 1, 400),
                    (5, 5, "A", 1, 500),
                    (6, 6, "B", 1, 500),
                    (7, 4, "C", 1, 999),
                    (8, 7, "A", 1, 0),
                    (9, 3, "B", 1, 10000),
                    (10, 8, "C", 1, 123),
                    (11, 11, "C", 1, 50),
                ],
            ),
        }
    if schema == "support":
        return {
            "agents": records(
                "id team",
                [
                    (1, "red"),
                    (2, "blue"),
                    (3, "red"),
                    (4, "green"),
                    (5, "blue"),
                    (6, "gold"),
                ],
            ),
            "tickets": records(
                "id agent_id opened_on resolved_on priority",
                [
                    (1, 1, "2025-01-01", None, 3),
                    (2, 1, "2025-01-15", "2025-02-01", 0),
                    (3, 2, "2024-12-31", None, 3),
                    (4, 2, "2025-01-31", "2025-01-31", 1),
                    (5, 3, "2025-01-15", "2025-02-02", 2),
                    (6, None, "2025-01-15", None, 0),
                    (7, 4, "2025-02-01", None, 2),
                    (8, 5, "2025-01-01", "2025-01-02", 0),
                    (9, 3, "2025-01-31", None, 3),
                    (10, 5, "2025-01-15", "2025-01-15", 1),
                ],
            ),
            "events": records(
                "id ticket_id kind happened_on",
                [
                    (1, 1, "reply", "2025-01-02"),
                    (2, 1, "reply", "2025-01-02"),
                    (3, 1, "note", "2025-01-01"),
                    (4, 2, "note", "2025-01-15"),
                    (5, 3, "reply", "2025-01-01"),
                    (6, 3, "reply", "2025-01-03"),
                    (7, 4, "note", "2025-01-31"),
                    (8, 4, "note", "2025-01-31"),
                    (9, 5, "reply", "2025-01-16"),
                    (10, 6, "reply", "2025-01-15"),
                    (11, 9, "reply", "2025-02-01"),
                ],
            ),
        }
    return {
        "accounts": records(
            "id plan active",
            [
                (1, "basic", 1),
                (2, "pro", 1),
                (3, "basic", 0),
                (4, "pro", 1),
                (5, "basic", 1),
                (6, "pro", 1),
                (7, "basic", 0),
            ],
        ),
        "invoices": records(
            "id account_id issued_on total_cents",
            [
                (1, 1, "2025-01-01", 1000),
                (2, 1, "2025-01-31", 500),
                (3, 2, "2024-12-31", 200),
                (4, 2, "2025-02-01", 1000),
                (5, 3, "2025-01-15", 0),
                (6, 4, "2025-02-01", 0),
                (7, 5, "2025-01-15", 300),
                (8, 5, "2025-01-16", 100),
            ],
        ),
        "payments": records(
            "id invoice_id amount_cents paid_on",
            [
                (1, 1, 300, "2025-01-02"),
                (2, 1, 700, "2025-01-02"),
                (3, 3, 400, "2025-01-01"),
                (4, 4, 100, "2025-02-02"),
                (5, 7, 500, "2025-01-16"),
                (6, 8, 100, "2025-01-17"),
            ],
        ),
    }


def anchor(schema):
    if schema == "commerce":
        return {
            "customers": records("id region", [(1, "north"), (2, "south")]),
            "orders": records(
                "id customer_id status ordered_on",
                [
                    (1, 1, "paid", "2025-01-10"),
                    (2, 1, "paid", "2025-01-20"),
                    (3, 2, "paid", "2025-01-11"),
                ],
            ),
            "lines": records(
                "id order_id sku quantity unit_cents",
                [(1, 1, "A", 1, 100), (2, 2, "B", 1, 200), (3, 3, "C", 1, 50)],
            ),
        }
    if schema == "support":
        return {
            "agents": records("id team", [(1, "red"), (2, "blue")]),
            "tickets": records(
                "id agent_id opened_on resolved_on priority",
                [
                    (1, 1, "2025-01-10", None, 3),
                    (2, 1, "2025-01-11", None, 0),
                    (3, 2, "2025-01-12", None, 2),
                ],
            ),
            "events": records(
                "id ticket_id kind happened_on",
                [
                    (1, 1, "reply", "2025-01-11"),
                    (2, 1, "reply", "2025-01-12"),
                    (3, 2, "reply", "2025-01-12"),
                ],
            ),
        }
    return {
        "accounts": records("id plan active", [(1, "basic", 1), (2, "pro", 1)]),
        "invoices": records(
            "id account_id issued_on total_cents",
            [(1, 1, "2025-01-10", 100), (2, 2, "2025-01-11", 200)],
        ),
        "payments": records(
            "id invoice_id amount_cents paid_on",
            [(1, 1, 100, "2025-01-12"), (2, 2, 200, "2025-01-13")],
        ),
    }


def generated(schema, seed):
    rng = random.Random(seed)
    dates = [
        "2024-12-31",
        "2025-01-01",
        "2025-01-15",
        "2025-01-31",
        "2025-02-01",
        "2025-02-02",
    ]
    if schema == "commerce":
        customers = records(
            "id region",
            [(i, rng.choice([None, "north", "south"])) for i in range(1, 9)],
        )
        orders = records(
            "id customer_id status ordered_on",
            [
                (
                    i,
                    rng.randrange(1, 8),
                    rng.choice(["paid", "paid", "pending", "cancelled"]),
                    rng.choice(dates),
                )
                for i in range(1, 19)
            ],
        )
        lines = []
        for order in orders:
            for _ in range(rng.randrange(4)):
                lines.append(
                    dict(
                        id=len(lines) + 1,
                        order_id=order["id"],
                        sku=rng.choice("ABC"),
                        quantity=rng.randrange(1, 6),
                        unit_cents=rng.choice([0, 50, 100, 333, 500]),
                    )
                )
        return dict(customers=customers, orders=orders, lines=lines)
    if schema == "support":
        agents = records(
            "id team", [(i, rng.choice(["red", "blue", "green"])) for i in range(1, 8)]
        )
        tickets, events = [], []
        for i in range(1, 19):
            opened = rng.choice(dates)
            later = [d for d in dates if d >= opened]
            tickets.append(
                dict(
                    id=i,
                    agent_id=rng.choice([None, 1, 2, 3, 4, 5, 6]),
                    opened_on=opened,
                    resolved_on=rng.choice([None] + later),
                    priority=rng.randrange(4),
                )
            )
            for _ in range(rng.randrange(4)):
                events.append(
                    dict(
                        id=len(events) + 1,
                        ticket_id=i,
                        kind=rng.choice(["reply", "note"]),
                        happened_on=rng.choice(later),
                    )
                )
        return dict(agents=agents, tickets=tickets, events=events)
    accounts = records(
        "id plan active",
        [(i, rng.choice(["basic", "pro"]), rng.randrange(2)) for i in range(1, 8)],
    )
    invoices, payments = [], []
    for i in range(1, 16):
        issued = rng.choice(dates)
        invoices.append(
            dict(
                id=i,
                account_id=rng.randrange(1, 7),
                issued_on=issued,
                total_cents=rng.choice([0, 100, 200, 500, 1000]),
            )
        )
        for _ in range(rng.randrange(4)):
            payments.append(
                dict(
                    id=len(payments) + 1,
                    invoice_id=i,
                    amount_cents=rng.choice([50, 100, 200, 700]),
                    paid_on=rng.choice([d for d in dates if d >= issued]),
                )
            )
    return dict(accounts=accounts, invoices=invoices, payments=payments)


def build_worlds():
    worlds = []
    for schema in ("commerce", "support", "billing"):
        for role, seed in [
            ("anchor", 17),
            ("edge", 41),
            ("generated", 73),
            ("generated", 101),
            ("generated", 137),
            ("empty", 211),
        ]:
            data = (
                anchor(schema)
                if role == "anchor"
                else edge(schema)
                if role == "edge"
                else generated(schema, seed)
            )
            if role == "empty":
                data = {table: [] for table in data}
            suffix = str(seed) if role == "generated" else role
            worlds.append(
                dict(
                    id=f"{schema}-{suffix}",
                    schema=schema,
                    seed=seed,
                    role=role,
                    tables=data,
                )
            )
    return worlds


def materialize(schema, world, destination):
    destination = Path(destination)
    # Reserve exclusively. A failed fixture is removed, never a prior database.
    destination.touch(exist_ok=False)
    try:
        with closing(sqlite3.connect(destination)) as db, db:
            db.execute("PRAGMA foreign_keys=ON")
            db.executescript(schema["ddl"])
            if set(world["tables"]) != set(schema["tables"]):
                raise ValueError("world tables differ from schema")
            for table, columns in schema["tables"].items():
                for row in world["tables"][table]:
                    if set(row) != set(columns):
                        raise ValueError("row columns differ")
                    for name, value in row.items():
                        if name.endswith("_on") and value is not None:
                            if date.fromisoformat(value).isoformat() != value:
                                raise ValueError("noncanonical date")
                    db.execute(
                        f"INSERT INTO {table} VALUES ({','.join('?' for _ in columns)})",
                        [row[c] for c in columns],
                    )
            if (
                world["schema"] == "support"
                and db.execute(
                    "SELECT 1 FROM events e JOIN tickets t ON e.ticket_id=t.id WHERE e.happened_on<t.opened_on"
                ).fetchone()
            ):
                raise ValueError("event precedes ticket")
            if (
                world["schema"] == "billing"
                and db.execute(
                    "SELECT 1 FROM payments p JOIN invoices i ON p.invoice_id=i.id WHERE p.paid_on<i.issued_on"
                ).fetchone()
            ):
                raise ValueError("payment precedes invoice")
            if db.execute("PRAGMA foreign_key_check").fetchall():
                raise ValueError("foreign key violation")
        destination.chmod(0o444)
    except BaseException:
        destination.unlink(missing_ok=True)
        raise


def load(root):
    root = Path(root)
    result = {}
    for name in ("tasks", "schemas", "worlds", "oracles", "controls"):
        path = root / "corpus" / (name + ".json")
        if path.exists():
            value = json.loads(path.read_text())
            if value["version"] != 1:
                raise ValueError("unsupported corpus version")
            result[name] = value[name]
    return result
