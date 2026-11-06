import hashlib
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from queryproof import freeze, imports

ROOT = Path(__file__).resolve().parents[1]


def fixture(folder):
    root = Path(folder) / "project"
    root.mkdir()
    for name in ("queryproof", "corpus"):
        shutil.copytree(
            ROOT / name, root / name, ignore=shutil.ignore_patterns("__pycache__")
        )
    (root / "docs").mkdir()
    shutil.copyfile(ROOT / "docs/task-contract.md", root / "docs/task-contract.md")
    (root / "evidence").mkdir()
    shutil.copyfile(
        ROOT / "evidence/independent-expected.json",
        root / "evidence/independent-expected.json",
    )
    shutil.copyfile(
        ROOT / "evidence/independent-control-adjudication.json",
        root / "evidence/independent-control-adjudication.json",
    )
    paths = [
        "corpus/tasks.json",
        "corpus/schemas.json",
        "corpus/worlds.json",
        "corpus/oracles.json",
        "docs/task-contract.md",
        "evidence/independent-expected.json",
    ]
    record = dict(
        version=1,
        status="passed",
        cells=144,
        input_sha256={
            p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in paths
        },
    )
    review = root / "evidence/test-agreement.json"
    review.write_text(json.dumps(record))
    frozen = Path(folder) / "freeze"
    freeze.create(root, frozen, review)
    return root, frozen


class FreezeTests(unittest.TestCase):
    def test_freeze_binds_source_worlds_and_planned_slots(self):
        with tempfile.TemporaryDirectory() as folder:
            root, frozen = fixture(folder)
            manifest = freeze.verify(root, frozen)
            self.assertEqual(24, len(manifest.get("planned_slots", [])))
            self.assertTrue((frozen / "public-prompt.txt").exists())
            (root / "corpus/worlds.json").write_text("{}")
            with self.assertRaises(ValueError):
                freeze.verify(root, frozen)

    def test_import_preserves_all_slots_and_malformed_sql(self):
        with tempfile.TemporaryDirectory() as folder:
            root, frozen = fixture(folder)
            raw = Path(folder) / "capture.json"
            raw.write_text(
                json.dumps(
                    dict(
                        version=1,
                        candidates=[
                            dict(id="answer1", task_id="C01", sql="SELECT '\ud800'")
                        ],
                    )
                )
            )
            destination = Path(folder) / "imported"
            result = imports.import_candidates(
                root, frozen, raw, destination, "agent_capture", "direct_v1"
            )
            self.assertEqual(24, len(result.get("slots", [])))
            self.assertEqual(1, len(result["candidates"]))
            self.assertEqual("invalid_sql", result["candidates"][0]["capture_error"])
            self.assertEqual(raw.read_bytes(), (destination / "raw.json").read_bytes())

    def test_duplicate_json_ids_and_unknown_tasks_rejected_without_publication(self):
        with tempfile.TemporaryDirectory() as folder:
            root, frozen = fixture(folder)
            raw = Path(folder) / "capture.json"
            destination = Path(folder) / "imported"
            for payload in [
                '{"version":1,"version":1,"candidates":[]}',
                json.dumps(
                    dict(
                        version=1,
                        candidates=[dict(id="x", task_id="unknown", sql="SELECT 1")],
                    )
                ),
                json.dumps(
                    dict(
                        version=1,
                        candidates=[dict(id="x", task_id="C01", sql="SELECT 1")] * 2,
                    )
                ),
            ]:
                raw.write_text(payload)
                with self.assertRaises(ValueError):
                    imports.import_candidates(
                        root, frozen, raw, destination, "authored_control", "controls"
                    )
                self.assertFalse(destination.exists())

    def test_modified_slots_limits_policy_or_prompt_cannot_redefine_freeze(self):
        with tempfile.TemporaryDirectory() as folder:
            root, frozen = fixture(folder)
            original = json.loads((frozen / "manifest.json").read_text())
            prompt = (frozen / "public-prompt.txt").read_bytes()
            for mutation in ("slots", "limits", "policy", "prompt"):
                with self.subTest(mutation=mutation):
                    value = copy.deepcopy(original)
                    (frozen / "public-prompt.txt").write_bytes(prompt)
                    if mutation == "slots":
                        value["planned_slots"] = []
                    if mutation == "limits":
                        value["limits"]["vm_operations"] = 1
                    if mutation == "policy":
                        value["policy"] = "different"
                    if mutation == "prompt":
                        changed = prompt + b"\nReturn no answers.\n"
                        (frozen / "public-prompt.txt").write_bytes(changed)
                        value["prompt_sha256"] = hashlib.sha256(changed).hexdigest()
                    (frozen / "manifest.json").write_text(json.dumps(value))
                    with self.assertRaises(ValueError):
                        freeze.verify(root, frozen)

    def test_stale_control_adjudication_cannot_freeze(self):
        with tempfile.TemporaryDirectory() as folder:
            root, frozen = fixture(folder)
            path = root / "evidence/independent-control-adjudication.json"
            value = json.loads(path.read_text())
            value["input_sha256"]["corpus/worlds.json"] = "0" * 64
            path.write_text(json.dumps(value))
            with self.assertRaises(ValueError):
                freeze.create(
                    root,
                    Path(folder) / "other-freeze",
                    root / "evidence/test-agreement.json",
                )

    def test_whole_malformed_model_capture_is_preserved_with_all_slots(self):
        with tempfile.TemporaryDirectory() as folder:
            root, frozen = fixture(folder)
            raw = Path(folder) / "raw.json"
            raw.write_bytes(b"{broken JSON")
            destination = Path(folder) / "imported"
            try:
                result = imports.import_candidates(
                    root, frozen, raw, destination, "agent_capture", "direct_v1"
                )
            except ValueError:
                result = {}
            self.assertEqual(24, len(result.get("slots", [])))
            self.assertEqual("invalid_json", result["capture_failure"])
            self.assertEqual(raw.read_bytes(), (destination / "raw.json").read_bytes())

    def test_non_string_task_id_is_failed_capture_not_typeerror(self):
        with tempfile.TemporaryDirectory() as folder:
            root, frozen = fixture(folder)
            raw = Path(folder) / "raw.json"
            raw.write_text(
                json.dumps(
                    dict(
                        version=1, candidates=[dict(id="x", task_id=[], sql="SELECT 1")]
                    )
                )
            )
            result = imports.import_candidates(
                root,
                frozen,
                raw,
                Path(folder) / "imported",
                "agent_capture",
                "direct_v1",
            )
            self.assertEqual("invalid_envelope", result["capture_failure"])
            self.assertEqual(24, len(result["slots"]))
