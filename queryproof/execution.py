"""Bounded local SQL execution and declared typed-result semantics."""

from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

STATUSES = {"ok", "policy", "limit", "timeout", "error", "worker_crash"}


def execute(db, sql, tables, timeout=2.0):
    start = time.monotonic()
    failure = dict(
        status="policy", rows=[], columns=0, error="SQL must be nonempty UTF-8 <=16 KiB"
    )
    try:
        valid_sql = (
            isinstance(sql, str)
            and bool(sql.strip())
            and len(sql.encode("utf-8")) <= 16384
            and "\x00" not in sql
        )
    except UnicodeEncodeError:
        valid_sql = False
    if not valid_sql:
        return failure
    if not 0 < timeout <= 2:
        raise ValueError("timeout must be in (0,2]")
    db = Path(db)
    source_hash = hashlib.sha256(db.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix="queryproof-worker-") as folder:
        copy = Path(folder) / "world.db"
        shutil.copyfile(db, copy)
        copy.chmod(0o444)
        request = json.dumps(dict(db=str(copy), sql=sql, tables=tables)).encode()
        with (
            tempfile.TemporaryFile() as stdin,
            tempfile.TemporaryFile() as stdout,
            tempfile.TemporaryFile() as stderr,
        ):
            stdin.write(request)
            stdin.seek(0)
            worker = subprocess.Popen(
                [sys.executable, "-I", str(Path(__file__).with_name("worker.py"))],
                stdin=stdin,
                stdout=stdout,
                stderr=stderr,
                cwd=folder,
                env={"LANG": "C.UTF-8"},
            )
            try:
                worker.wait(timeout=timeout)
                stdout.seek(0)
                raw = stdout.read(300001)
                if len(raw) > 300000:
                    result = dict(
                        status="limit",
                        rows=[],
                        columns=0,
                        error="worker output limit exceeded",
                    )
                elif worker.returncode != 0:
                    stderr.seek(0)
                    result = dict(
                        status="worker_crash",
                        rows=[],
                        columns=0,
                        error="worker exit "
                        + str(worker.returncode)
                        + ": "
                        + stderr.read(512).decode("utf-8", "replace"),
                    )
                else:
                    try:
                        result = json.loads(raw)
                        if (
                            not isinstance(result, dict)
                            or set(result) != {"status", "rows", "columns", "error"}
                            or result["status"] not in STATUSES
                            or type(result["columns"]) is not int
                            or not 0 <= result["columns"] <= 32
                            or not isinstance(result["rows"], list)
                            or len(result["rows"]) > 1000
                        ):
                            raise ValueError("malformed worker response")
                    except (ValueError, TypeError, KeyError):
                        result = dict(
                            status="worker_crash",
                            rows=[],
                            columns=0,
                            error="malformed worker response",
                        )
            except subprocess.TimeoutExpired:
                worker.kill()
                worker.wait()
                result = dict(
                    status="timeout",
                    rows=[],
                    columns=0,
                    error="parent wall deadline exceeded",
                )
            finally:
                if worker.poll() is None:
                    worker.kill()
                    worker.wait()
            result["worker_pid"] = worker.pid
    if hashlib.sha256(db.read_bytes()).hexdigest() != source_hash:
        raise RuntimeError("source database changed")
    result["elapsed_seconds"] = time.monotonic() - start
    return result


def _valid(rows, columns):
    if not isinstance(rows, list) or len(rows) > 1000:
        return False
    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) != len(columns):
            return False
        for value, col in zip(row, columns, strict=True):
            if value is None:
                if not col["nullable"]:
                    return False
            elif col["type"] == "integer":
                if type(value) is not int:
                    return False
            elif col["type"] == "text":
                if type(value) is not str:
                    return False
            elif col["type"] == "real":
                if type(value) not in (int, float) or not math.isfinite(value):
                    return False
            else:
                return False
    return True


def compare_result(task, expected, actual):
    def verdict(ok, reason):
        return {"pass": ok, "reason": reason}

    columns = task["columns"]
    if not _valid(expected, columns):
        raise ValueError("oracle violates task result types")
    if actual.get("status") != "ok":
        return verdict(
            False,
            "execution " + str(actual.get("status")) + ": " + str(actual.get("error")),
        )
    observed = actual.get("rows")
    if actual.get("columns") != len(columns) or not _valid(observed, columns):
        return verdict(False, "column shape or declared type mismatch")
    if len(observed) != len(expected):
        return verdict(
            False,
            f"row multiplicity differs: expected {len(expected)}, observed {len(observed)}",
        )

    def matches(left, right):
        for a, b, col in zip(left, right, columns, strict=True):
            if a is None or b is None:
                if a is not b:
                    return False
            elif col["type"] == "real":
                if not math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9):
                    return False
            elif a != b:
                return False
        return True

    if task["ordered"]:
        same = all(matches(a, b) for a, b in zip(expected, observed, strict=True))
    elif not any(c["type"] == "real" for c in columns):
        same = Counter(map(tuple, expected)) == Counter(map(tuple, observed))
    else:
        if len(expected) > 200:
            return verdict(False, "approximate bag matching limit (200 rows)")
        # Augmenting paths find a perfect matching; no greedy row removal or rounding.
        edges = [[j for j, b in enumerate(observed) if matches(a, b)] for a in expected]
        assigned = {}

        def augment(i, seen):
            for j in edges[i]:
                if j in seen:
                    continue
                seen.add(j)
                if j not in assigned or augment(assigned[j], seen):
                    assigned[j] = i
                    return True
            return False

        same = all(augment(i, set()) for i in range(len(expected)))
    return verdict(
        same,
        "matches declared result semantics"
        if same
        else "ordered rows differ"
        if task["ordered"]
        else "typed result bag differs",
    )
