import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from queryproof import report, runs, imports
from test_freeze import fixture, ROOT
from test_runs import imported_fixture


class ProductTests(unittest.TestCase):
    def cli(self, root, *args):
        return subprocess.run(
            [sys.executable, "-m", "queryproof", "--root", str(root), *map(str, args)],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )

    def test_real_cli_task_run_inspect_compare_and_report(self):
        with tempfile.TemporaryDirectory() as folder:
            root, frozen = fixture(folder)
            imported = imported_fixture(folder, root, frozen)
            run = Path(folder) / "run"
            task = self.cli(root, "task", "C01")
            self.assertEqual(0, task.returncode, task.stderr)
            self.assertIn("zero", json.loads(task.stdout)["prompt"])
            evaluated = self.cli(
                root, "run", "--freeze", frozen, "--imported", imported, "--out", run
            )
            self.assertEqual(0, evaluated.returncode, evaluated.stderr)
            inspected = self.cli(root, "inspect", run, "C01-mutant")
            self.assertEqual(0, inspected.returncode, inspected.stderr)
            detail = json.loads(inspected.stdout)
            self.assertEqual("commerce-edge", detail["counterexample"]["world"]["id"])
            self.assertEqual(7, len(detail["counterexample"]["expected_rows"]))
            compared = self.cli(root, "compare", run)
            self.assertEqual(0, compared.returncode, compared.stderr)
            summary = json.loads(compared.stdout)["runs"][0]
            self.assertEqual(1, summary["graders"]["single"]["false_accepts"])
            self.assertEqual(0, summary["graders"]["multi"]["false_accepts"])
            self.assertEqual(1, summary["graders"]["exact"]["false_rejects"])
            output = Path(folder) / "report.html"
            rendered = self.cli(root, "report", run, "--html-out", output)
            self.assertEqual(0, rendered.returncode, rendered.stderr)
            self.assertIn("commerce-edge", output.read_text())
            self.assertIn("C01-mutant", output.read_text())

    def test_model_primary_rate_includes_missing_and_invalid_slots(self):
        with tempfile.TemporaryDirectory() as folder:
            root, frozen = fixture(folder)
            imported = imported_fixture(folder, root, frozen, True)
            run = Path(folder) / "run"
            runs.evaluate(root, frozen, imported, run)
            summary = report.summarize(root, run)
            self.assertEqual(24, summary.get("primary_model_denominator"))
            self.assertEqual(0, summary["primary_model_successes"])
            self.assertFalse(summary["capture_complete"])
            self.assertEqual(23, summary["missing_slots"])

    def test_report_escapes_untrusted_text(self):
        summary = dict(title="<script>alert(1)</script>")
        rendered = report.html(summary, [dict(sql="<script>alert(2)</script>")])
        self.assertIn("&lt;script&gt;", rendered)
        self.assertNotIn("<script>", rendered)

    def test_model_headline_uses_planned_denominator_not_calibration(self):
        summary = dict(
            kind="agent_capture",
            primary_model_successes=3,
            primary_model_denominator=24,
            completed_worlds=144,
            planned_worlds=144,
            executed_worlds=18,
            missing_slots=20,
            invalid_slots=1,
            capture_failure=None,
            model_by_split={
                "dev": dict(successes=2, planned=12),
                "assessment": dict(successes=1, planned=12),
            },
        )
        rendered = report.html(summary, [])
        headline = rendered.split("<details>", 1)[0]
        self.assertIn("3 / 24", headline)
        self.assertIn("20 missing", headline)
        self.assertNotIn("Grader calibration", headline)

    def test_malformed_whole_capture_reaches_report_as_zero_of_24(self):
        with tempfile.TemporaryDirectory() as folder:
            root, frozen = fixture(folder)
            raw = Path(folder) / "broken.json"
            raw.write_bytes(b"{not json")
            imported = Path(folder) / "import"
            imports.import_candidates(
                root, frozen, raw, imported, "agent_capture", "direct_v1"
            )
            run = Path(folder) / "run"
            runs.evaluate(root, frozen, imported, run)
            summary = report.summarize(root, run)
            self.assertEqual(24, summary["primary_model_denominator"])
            self.assertEqual(0, summary["primary_model_successes"])
            self.assertEqual(24, summary["invalid_slots"])
            self.assertEqual(0, summary["executed_worlds"])
            self.assertEqual("invalid_json", summary["capture_failure"])
            self.assertIn("0 / 24", report.html(summary, []))
