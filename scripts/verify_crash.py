"""Run a real SIGKILL/resume drill; save byte-preservation evidence."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from queryproof import imports, runs  # noqa: E402
from queryproof.storage import CACHE, encoded, file_sha, guard, publish  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    if not imports.ID.fullmatch(args.tag):
        raise ValueError("invalid tag")
    guard()
    folder = CACHE / "crash-drills" / args.tag
    folder.mkdir(parents=True, exist_ok=False)
    candidates = json.loads((ROOT / "corpus/controls.json").read_text())["controls"]
    raw = folder / "raw.json"
    publish(raw, encoded(dict(version=1, candidates=[c for c in candidates if c["task_id"] == "C01"])))
    imported, destination = folder / "import", folder / "run"
    imports.import_candidates(ROOT, args.freeze, raw, imported, "authored_control", args.tag)
    command = [sys.executable, "-m", "queryproof", "--root", str(ROOT), "run", "--freeze", str(args.freeze.resolve()), "--imported", str(imported), "--out", str(destination)]
    with (folder / "stdout.txt").open("wb") as stdout, (folder / "stderr.txt").open("wb") as stderr:
        process = subprocess.Popen(command, cwd=ROOT, stdout=stdout, stderr=stderr)
        try:
            deadline = time.monotonic() + 10
            while process.poll() is None and time.monotonic() < deadline and len(list((destination / "results").glob("*.json"))) < 2:
                time.sleep(0.01)
            before = {p.name: file_sha(p) for p in (destination / "results").glob("*.json")}
            if process.poll() is not None or not before:
                raise RuntimeError("did not observe running evaluator with committed outcomes")
            process.kill()
            process.wait(timeout=3)
            partial = runs.read(ROOT, destination)
            complete = runs.evaluate(ROOT, args.freeze, imported, destination)
            preserved = all(file_sha(destination / "results" / name) == digest for name, digest in before.items())
            if partial["complete"] or not complete["complete"] or not preserved:
                raise AssertionError("crash/resume contract failed")
            record = dict(version=1,method="actual SIGKILL of running CLI evaluator followed by same-path resume",returncode=process.returncode,frozen_sha256=file_sha(args.freeze / "manifest.json"),script_sha256=file_sha(Path(__file__)),committed_before_kill=before,partial_completed_worlds=partial["completed_worlds"],partial_complete=partial["complete"],resumed_completed_worlds=complete["completed_worlds"],resumed_planned_worlds=complete["planned_worlds"],resumed_complete=complete["complete"],all_prior_result_bytes_preserved=preserved,run_sha256=complete["run_sha256"],run_path=str(destination))
            publish(args.evidence, encoded(record))
            print(json.dumps({k: v for k, v in record.items() if k != "committed_before_kill"}, indent=2))
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()


if __name__ == "__main__":
    main()
