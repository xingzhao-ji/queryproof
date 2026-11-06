import fcntl
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from queryproof import imports, runs
from test_freeze import fixture


def imported_fixture(folder, root, frozen, model=False):
    raw = Path(folder) / "raw.json"
    if model:
        candidates = [dict(id="C01", task_id="C01", sql="SELECT '\ud800'")]
    else:
        pool = json.loads((root / "corpus/controls.json").read_text())["controls"]
        candidates = [
            c for c in pool if c["id"] in ["C01-gold", "C01-equiv", "C01-mutant"]
        ]
    raw.write_text(json.dumps(dict(version=1, candidates=candidates)))
    destination = Path(folder) / "import"
    imports.import_candidates(
        root,
        frozen,
        raw,
        destination,
        "agent_capture" if model else "authored_control",
        "direct_v1" if model else "controls",
    )
    return destination


class RunTests(unittest.TestCase):
    def test_evaluate_resume_keeps_result_bytes_and_detects_corruption(self):
        with tempfile.TemporaryDirectory() as folder:
            root, frozen = fixture(folder)
            imported = imported_fixture(folder, root, frozen)
            destination = Path(folder) / "run"
            result = runs.evaluate(root, frozen, imported, destination)
            self.assertTrue(result.get("complete", False))
            self.assertEqual(18, result["completed_worlds"])
            before = {
                p.name: p.read_bytes() for p in (destination / "results").glob("*.json")
            }
            runs.evaluate(root, frozen, imported, destination)
            self.assertEqual(
                before,
                {
                    p.name: p.read_bytes()
                    for p in (destination / "results").glob("*.json")
                },
            )
            next((destination / "results").glob("*.json")).write_text("{}")
            with self.assertRaises(ValueError):
                runs.read(root, destination)

    def test_missing_and_malformed_model_answers_keep_all_24_slots(self):
        with tempfile.TemporaryDirectory() as folder:
            root, frozen = fixture(folder)
            imported = imported_fixture(folder, root, frozen, True)
            result = runs.evaluate(root, frozen, imported, Path(folder) / "run")
            self.assertEqual(24, result.get("planned_slots"))
            self.assertEqual(144, result["completed_worlds"])
            self.assertEqual(
                23, sum(c["capture_error"] == "missing" for c in result["candidates"])
            )
            self.assertEqual(
                1,
                sum(c["capture_error"] == "invalid_sql" for c in result["candidates"]),
            )

    def test_concurrent_writer_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            root, frozen = fixture(folder)
            imported = imported_fixture(folder, root, frozen)
            destination = Path(folder) / "run"
            destination.mkdir()
            with (destination / "run.lock").open("w") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with self.assertRaises(ValueError):
                    runs.evaluate(root, frozen, imported, destination)

    def test_real_sigkill_then_resume_preserves_committed_outcomes(self):
        with tempfile.TemporaryDirectory() as folder:
            root, frozen = fixture(folder)
            imported = imported_fixture(folder, root, frozen)
            destination = Path(folder) / "run"
            command = [
                sys.executable,
                "-c",
                "from pathlib import Path;from queryproof.runs import evaluate;import sys;evaluate(*map(Path,sys.argv[1:]))",
                str(root),
                str(frozen),
                str(imported),
                str(destination),
            ]
            process = subprocess.Popen(
                command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
            )
            deadline = time.monotonic() + 8
            try:
                while (
                    time.monotonic() < deadline
                    and process.poll() is None
                    and len(list((destination / "results").glob("*.json"))) < 2
                ):
                    time.sleep(0.01)
                before = {
                    p.name: p.read_bytes()
                    for p in (destination / "results").glob("*.json")
                }
                self.assertGreater(len(before), 0)
                self.assertIsNone(
                    process.poll(), "run should still be executing when killed"
                )
                process.kill()
                process.wait(timeout=3)
                partial = runs.read(root, destination)
                self.assertFalse(partial["complete"])
                result = runs.evaluate(root, frozen, imported, destination)
                self.assertTrue(result["complete"])
                for name, data in before.items():
                    self.assertEqual(
                        data, (destination / "results" / name).read_bytes()
                    )
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
                process.stderr.close()
