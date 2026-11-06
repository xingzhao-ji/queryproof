"""Reviewable task → import → execute/resume → counterexample workflow."""

import argparse
import json
from pathlib import Path
import sys
from . import freeze, imports, runs, report
from .corpus import load
from .storage import encoded, publish


def main(argv=None):
    parser = argparse.ArgumentParser(prog="queryproof")
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("tasks")
    task = commands.add_parser("task")
    task.add_argument("id")
    f = commands.add_parser("freeze")
    f.add_argument("--out", type=Path, required=True)
    f.add_argument("--oracle-review", type=Path)
    imp = commands.add_parser("import-candidates")
    for name in ("freeze", "input", "out"):
        imp.add_argument("--" + name, type=Path, required=True)
    imp.add_argument("--kind", choices=sorted(imports.KINDS), required=True)
    imp.add_argument("--cohort", required=True)
    run = commands.add_parser("run")
    for name in ("freeze", "imported", "out"):
        run.add_argument("--" + name, type=Path, required=True)
    r = commands.add_parser("report")
    r.add_argument("run", type=Path)
    r.add_argument("--json-out", type=Path)
    r.add_argument("--html-out", type=Path)
    i = commands.add_parser("inspect")
    i.add_argument("run", type=Path)
    i.add_argument("candidate_id")
    c = commands.add_parser("compare")
    c.add_argument("runs", type=Path, nargs="+")
    args = parser.parse_args(argv)
    try:
        if args.command in {"task", "tasks"}:
            data = load(args.root)
            if args.command == "tasks":
                result = data["tasks"]
            else:
                result = next((t for t in data["tasks"] if t["id"] == args.id), None)
                if result is None:
                    raise ValueError("unknown task")
        elif args.command == "freeze":
            result = freeze.create(
                args.root,
                args.out,
                args.oracle_review
                or args.root / "evidence/independent-oracle-review.json",
            )
        elif args.command == "import-candidates":
            result = imports.import_candidates(
                args.root, args.freeze, args.input, args.out, args.kind, args.cohort
            )
        elif args.command == "run":
            state = runs.evaluate(args.root, args.freeze, args.imported, args.out)
            result = {
                k: state[k]
                for k in (
                    "run_sha256",
                    "planned_slots",
                    "planned_worlds",
                    "completed_worlds",
                    "complete",
                )
            }
        elif args.command == "inspect":
            result = report.inspect(args.root, args.run, args.candidate_id)
        elif args.command == "compare":
            result = report.compare(args.root, args.runs)
        else:
            result = report.summarize(args.root, args.run)
            if args.json_out:
                publish(args.json_out, encoded(result))
            if args.html_out:
                diagnostics = [
                    report.inspect(args.root, args.run, c["id"])
                    for c in result["candidates"]
                ]
                publish(args.html_out, report.html(result, diagnostics).encode())
        sys.stdout.write(encoded(result).decode())
        return 0
    except (ValueError, OSError, KeyError, TypeError) as error:
        sys.stderr.write(
            json.dumps(
                dict(error=type(error).__name__, message=str(error)), ensure_ascii=True
            )
            + "\n"
        )
        return 2
