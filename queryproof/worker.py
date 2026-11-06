"""Trusted subprocess entry point. Not an OS sandbox; accepts SQL, never Python."""

from contextlib import closing
import json
import math
from pathlib import Path
import resource
import sqlite3
import sys

FUNCTIONS = frozenset(
    {
        "count",
        "sum",
        "avg",
        "min",
        "max",
        "coalesce",
        "ifnull",
        "nullif",
        "total",
        "substr",
        "substring",
        "length",
        "lower",
        "upper",
        "abs",
        "round",
        "row_number",
        "rank",
        "dense_rank",
        "lag",
        "lead",
    }
)


def run(request):
    denied = False
    exhausted = False
    operations = 0
    tables = set(request["tables"])

    def authorize(action, one, two, database, trigger):
        nonlocal denied
        allowed = action in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_RECURSIVE)
        if action == sqlite3.SQLITE_READ:
            # SQLite also emits a table-level read with an empty column and
            # database=None (e.g. count/optimizer scans). No attached/temp DB exists.
            allowed = one in tables and (
                database == "main" or database is None and two == ""
            )
        elif action == sqlite3.SQLITE_FUNCTION:
            allowed = (two or "").lower() in FUNCTIONS
        if not allowed:
            denied = True
        return sqlite3.SQLITE_OK if allowed else sqlite3.SQLITE_DENY

    def progress():
        nonlocal exhausted, operations
        operations += 1000
        exhausted = operations >= 200000
        return int(exhausted)

    with closing(
        sqlite3.connect(Path(request["db"]).as_uri() + "?mode=ro", uri=True)
    ) as db:
        db.enable_load_extension(False)
        db.execute("PRAGMA query_only=ON")
        db.execute("PRAGMA trusted_schema=OFF")
        limits = {
            "LENGTH": 32768,
            "SQL_LENGTH": 16384,
            "COLUMN": 32,
            "EXPR_DEPTH": 50,
            "COMPOUND_SELECT": 16,
            "VDBE_OP": 10000,
            "FUNCTION_ARG": 16,
            "ATTACHED": 0,
            "LIKE_PATTERN_LENGTH": 128,
            "VARIABLE_NUMBER": 0,
            "WORKER_THREADS": 0,
        }
        for name, limit in limits.items():
            db.setlimit(getattr(sqlite3, "SQLITE_LIMIT_" + name), limit)
        db.set_authorizer(authorize)
        db.set_progress_handler(progress, 1000)
        try:
            cursor = db.execute(request["sql"])
            if cursor.description is None:
                return dict(
                    status="policy",
                    columns=0,
                    rows=[],
                    error="not a result-producing SELECT",
                )
            columns = len(cursor.description)
            rows, used = [], 2
            for row in cursor:
                if len(rows) >= 1000:
                    return dict(
                        status="limit",
                        columns=columns,
                        rows=[],
                        error="row limit exceeded",
                    )
                for cell in row:
                    if isinstance(cell, bytes):
                        return dict(
                            status="policy",
                            columns=columns,
                            rows=[],
                            error="BLOB results unsupported",
                        )
                    if isinstance(cell, str) and len(cell.encode("utf-8")) > 16384:
                        return dict(
                            status="limit",
                            columns=columns,
                            rows=[],
                            error="cell byte limit exceeded",
                        )
                    if isinstance(cell, float) and not math.isfinite(cell):
                        return dict(
                            status="error",
                            columns=columns,
                            rows=[],
                            error="non-finite result",
                        )
                encoded = json.dumps(
                    row, ensure_ascii=True, allow_nan=False, separators=(",", ":")
                )
                used += len(encoded) + 1
                if used > 262144:
                    return dict(
                        status="limit",
                        columns=columns,
                        rows=[],
                        error="result byte limit exceeded",
                    )
                rows.append(list(row))
            return dict(status="ok", columns=columns, rows=rows, error=None)
        except (sqlite3.Error, MemoryError) as error:
            status = (
                "policy"
                if denied
                else "limit"
                if exhausted or isinstance(error, (MemoryError, sqlite3.DataError))
                else "error"
            )
            return dict(
                status=status,
                columns=0,
                rows=[],
                error=str(error)[:240] or "SQLite resource limit",
            )


def main():
    # Native allocator isolation is NOT claimed. File output, CPU, descriptors are capped.
    resource.setrlimit(resource.RLIMIT_CPU, (1, 2))
    resource.setrlimit(resource.RLIMIT_FSIZE, (524288, 524288))
    resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    raw = sys.stdin.buffer.read(65537)
    if len(raw) > 65536:
        raise ValueError("oversized request")
    result = run(json.loads(raw))
    sys.stdout.write(
        json.dumps(result, ensure_ascii=True, allow_nan=False, separators=(",", ":"))
    )


if __name__ == "__main__":
    main()
