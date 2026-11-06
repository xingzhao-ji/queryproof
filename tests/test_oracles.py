from pathlib import Path
import tempfile
import unittest
from queryproof.corpus import load, materialize
from queryproof.execution import execute, compare_result

ROOT = Path(__file__).resolve().parents[1]


class OracleTests(unittest.TestCase):
    def test_gold_and_control_coverage(self):
        data = load(ROOT)
        self.assertIn("oracles", data)
        self.assertEqual({t["id"] for t in data["tasks"]}, set(data["oracles"]))
        self.assertEqual(72, len(data["controls"]))
        self.assertEqual(72, len({c["id"] for c in data["controls"]}))

    def test_hand_computed_edge_results(self):
        data = load(ROOT)
        self.assertIn("oracles", data)
        cases = {
            "C01": [[1, 1000], [2, 1000], [3, 999], [4, 0], [5, 0], [6, 50], [7, 0]],
            "S02": [[5], [6]],
            "B06": [
                [1, 1, 300],
                [1, 2, 1000],
                [3, 3, 400],
                [4, 4, 100],
                [7, 5, 500],
                [8, 6, 100],
            ],
        }
        with tempfile.TemporaryDirectory() as folder:
            for task_id, expected in cases.items():
                task = next(t for t in data["tasks"] if t["id"] == task_id)
                world = next(
                    w for w in data["worlds"] if w["id"] == task["schema"] + "-edge"
                )
                db = Path(folder) / (task_id + ".db")
                schema = data["schemas"][task["schema"]]
                materialize(schema, world, db)
                result = execute(db, data["oracles"][task_id], list(schema["tables"]))
                self.assertTrue(compare_result(task, expected, result)["pass"], result)
