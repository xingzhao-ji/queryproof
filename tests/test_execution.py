from pathlib import Path
import hashlib
import os
import tempfile
import unittest

from queryproof.corpus import load, materialize
from queryproof.execution import execute, compare_result

ROOT = Path(__file__).resolve().parents[1]


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "world.db"
        corpus = load(ROOT)
        world = next(w for w in corpus["worlds"] if w["id"] == "commerce-edge")
        materialize(corpus["schemas"]["commerce"], world, self.db)
        self.tables = ["customers", "orders", "lines"]

    def test_actual_query_and_source_unchanged(self):
        before = hashlib.sha256(self.db.read_bytes()).hexdigest()
        result = execute(self.db, "SELECT id FROM customers ORDER BY id", self.tables)
        self.assertEqual("ok", result["status"])
        self.assertEqual([[1], [2], [3], [4], [5], [6], [7]], result["rows"])
        self.assertEqual(before, hashlib.sha256(self.db.read_bytes()).hexdigest())

    def test_authorizer_rejects_write_attach_schema_pragma_and_functions(self):
        for sql in [
            "DELETE FROM customers",
            "ATTACH ':memory:' AS x",
            "SELECT name FROM sqlite_schema",
            "PRAGMA table_info(customers)",
            "SELECT load_extension('x')",
            "SELECT randomblob(100)",
            "SELECT * FROM pragma_table_info('customers')",
            "WITH x AS (SELECT * FROM sqlite_master) SELECT * FROM x",
        ]:
            with self.subTest(sql=sql):
                self.assertEqual("policy", execute(self.db, sql, self.tables)["status"])

    def test_multiple_statements_and_unknown_table_fail(self):
        self.assertNotEqual(
            "ok",
            execute(self.db, "SELECT 1; DELETE FROM customers", self.tables)["status"],
        )
        self.assertEqual(
            "policy", execute(self.db, "SELECT * FROM lines", ["customers"])["status"]
        )

    def test_vm_and_row_limits(self):
        expensive = "WITH RECURSIVE n(x) AS (VALUES(1) UNION ALL SELECT x+1 FROM n) SELECT sum(x) FROM n"
        self.assertEqual("limit", execute(self.db, expensive, self.tables)["status"])
        rows = "SELECT a.id FROM customers a,customers b,customers c,customers d"
        self.assertEqual("limit", execute(self.db, rows, self.tables)["status"])

    def test_cell_and_total_bytes_bounded_before_accumulation(self):
        value = "a" * 9000
        cell = "WITH v(x) AS (SELECT '" + value + "') SELECT x||x FROM v"
        total = (
            "WITH v(x) AS (SELECT '"
            + value
            + "') SELECT x,x,x FROM v,customers a,customers b"
        )
        self.assertEqual("limit", execute(self.db, cell, self.tables)["status"])
        result = execute(self.db, total, self.tables)
        self.assertEqual("limit", result["status"])
        self.assertLess(len(str(result)), 2048)

    def test_wall_deadline_reaps_actual_child(self):
        result = execute(self.db, "SELECT 1", self.tables, timeout=0.00001)
        self.assertEqual("timeout", result["status"])
        with self.assertRaises(ProcessLookupError):
            os.kill(result["worker_pid"], 0)

    def test_unpaired_surrogate_is_policy_result_not_parent_exception(self):
        result = execute(self.db, "SELECT '\ud800'", self.tables)
        self.assertEqual("policy", result["status"])


class ComparisonTests(unittest.TestCase):
    def task(self, types, ordered=False, nullable=False):
        return dict(
            ordered=ordered, columns=[dict(type=t, nullable=nullable) for t in types]
        )

    def actual(self, rows, columns=1):
        return dict(status="ok", rows=rows, columns=columns)

    def test_bag_preserves_duplicates_but_not_order(self):
        task = self.task(["integer"])
        self.assertTrue(
            compare_result(task, [[1], [1], [2]], self.actual([[2], [1], [1]]))["pass"]
        )
        self.assertFalse(
            compare_result(task, [[1], [1], [2]], self.actual([[2], [1]]))["pass"]
        )
        self.assertFalse(
            compare_result(
                self.task(["integer"], True), [[1], [2]], self.actual([[2], [1]])
            )["pass"]
        )

    def test_types_null_empty_columns_and_failed_execution(self):
        task = self.task(["integer"])
        for rows in [[["1"]], [[1.0]], [[None]], [[True]]]:
            self.assertFalse(compare_result(task, [[1]], self.actual(rows))["pass"])
        self.assertTrue(compare_result(task, [], self.actual([]))["pass"])
        self.assertFalse(compare_result(task, [], self.actual([], 2))["pass"])
        self.assertFalse(
            compare_result(task, [], dict(status="timeout", rows=[], columns=1))["pass"]
        )
        self.assertTrue(
            compare_result(
                self.task(["integer"], nullable=True), [[None]], self.actual([[None]])
            )["pass"]
        )

    def test_numeric_bag_finds_perfect_matching_not_greedy_or_rounding(self):
        task = self.task(["real"])
        # First expected can match either actual; second can only match the first.
        expected = [[1.0], [1.0 + 1.5e-9]]
        actual = self.actual([[1.0 + 0.8e-9], [1.0 - 0.8e-9]])
        self.assertTrue(compare_result(task, expected, actual)["pass"])
        self.assertFalse(
            compare_result(task, [[1.0], [1.0]], self.actual([[1.0], [1.0 + 2e-8]]))[
                "pass"
            ]
        )
        self.assertFalse(
            compare_result(task, [[1.0]], self.actual([[float("nan")]]))["pass"]
        )


if __name__ == "__main__":
    unittest.main()
