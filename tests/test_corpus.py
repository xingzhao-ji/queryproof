import json
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

from queryproof import corpus

ROOT = Path(__file__).resolve().parents[1]


class CorpusTests(unittest.TestCase):
    def test_worlds_include_anchor_edge_empty_and_reproduce(self):
        worlds = corpus.build_worlds()
        self.assertEqual(18, len(worlds))
        self.assertEqual(worlds, corpus.build_worlds())
        for schema in ("commerce", "support", "billing"):
            selected = [w for w in worlds if w["schema"] == schema]
            self.assertEqual(6, len(selected))
            self.assertEqual(
                ["anchor", "edge", "generated", "generated", "generated", "empty"],
                [w["role"] for w in selected],
            )
            self.assertTrue(all(not rows for rows in selected[-1]["tables"].values()))

    def test_real_database_constraints_and_no_overwrite(self):
        schemas = json.loads((ROOT / "corpus/schemas.json").read_text())["schemas"]
        with tempfile.TemporaryDirectory() as folder:
            for world in corpus.build_worlds():
                path = Path(folder) / (world["id"] + ".db")
                corpus.materialize(schemas[world["schema"]], world, path)
                self.assertTrue(path.exists())
                with closing(sqlite3.connect(path)) as db:
                    self.assertEqual(
                        [], db.execute("PRAGMA foreign_key_check").fetchall()
                    )
                    self.assertEqual(
                        "ok", db.execute("PRAGMA integrity_check").fetchone()[0]
                    )
                with self.assertRaises(FileExistsError):
                    corpus.materialize(schemas[world["schema"]], world, path)

    def test_edge_rows_cover_nulls_multiplicity_and_tied_revenue(self):
        worlds = {w["id"]: w["tables"] for w in corpus.build_worlds()}
        self.assertIn("commerce-edge", worlds)
        c = worlds["commerce-edge"]
        self.assertIsNone(c["customers"][2]["region"])
        self.assertGreater(sum(r["order_id"] == 1 for r in c["lines"]), 1)
        self.assertFalse(any(r["order_id"] == 10 for r in c["lines"]))
        self.assertTrue(
            any(r["agent_id"] is None for r in worlds["support-edge"]["tickets"])
        )


if __name__ == "__main__":
    unittest.main()
