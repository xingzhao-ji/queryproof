"""Immutable per-world outcomes with advisory single-writer locking and resume."""

import fcntl
import os
from pathlib import Path
import tempfile
from . import freeze, imports
from .corpus import load, materialize
from .execution import execute, compare_result, STATUSES
from .storage import (
    encoded,
    file_sha,
    guard,
    publish,
    publish_json,
    read_bytes,
    read_json,
    sha,
)


def _candidates(canonical):
    if canonical["kind"] != "agent_capture":
        return canonical["candidates"]
    by_task = {c["task_id"]: c for c in canonical["candidates"]}
    return [
        by_task.get(
            slot["task_id"],
            dict(
                id="_missing_" + slot["task_id"],
                task_id=slot["task_id"],
                sql=None,
                capture_error="invalid_capture"
                if canonical["capture_failure"]
                else "missing",
            ),
        )
        for slot in canonical["slots"]
    ]


def _name(candidate, world):
    return candidate["task_id"] + "--" + candidate["id"] + "--" + world["id"] + ".json"


def _publish_same(path, data):
    if path.exists():
        if read_bytes(path, 4 * 1024 * 1024) != data:
            raise ValueError("partial run contains conflicting immutable input")
    else:
        publish(path, data)


def _initialize(root, frozen, imported, destination, canonical):
    corpus = load(root)
    files = {}
    for source, prefix, names in [
        (Path(frozen), "frozen", ["manifest.json", "public-prompt.txt"]),
        (Path(imported), "input", ["manifest.json", "raw.json", "candidates.json"]),
    ]:
        for name in names:
            target = destination / prefix / name
            _publish_same(target, read_bytes(source / name, 2 * 1024 * 1024))
            files[str(target.relative_to(destination))] = file_sha(target)
    with tempfile.TemporaryDirectory(prefix="queryproof-worlds-") as folder:
        for world in corpus["worlds"]:
            source = Path(folder) / (world["id"] + ".db")
            materialize(corpus["schemas"][world["schema"]], world, source)
            target = destination / "worlds" / source.name
            _publish_same(target, read_bytes(source))
            files[str(target.relative_to(destination))] = file_sha(target)
    manifest = dict(
        version=1,
        files=files,
        frozen_sha256=file_sha(Path(frozen) / "manifest.json"),
        import_sha256=file_sha(Path(imported) / "manifest.json"),
        kind=canonical["kind"],
        cohort=canonical["cohort"],
    )
    _publish_same(destination / "manifest.json", encoded(manifest))


def read(root, destination):
    root, destination = Path(root), Path(destination)
    try:
        manifest = read_json(destination / "manifest.json")
        frozen_manifest = freeze.verify(root, destination / "frozen")
        if (
            manifest["version"] != 1
            or manifest["frozen_sha256"]
            != file_sha(destination / "frozen/manifest.json")
            or manifest["import_sha256"]
            != file_sha(destination / "input/manifest.json")
        ):
            raise ValueError("run provenance mismatch")
        for name, digest in manifest["files"].items():
            path = (destination / name).resolve()
            if (
                not path.is_relative_to(destination.resolve())
                or file_sha(path) != digest
            ):
                raise ValueError("run input/database changed: " + name)
        canonical = imports.verify(
            destination / "input", manifest["frozen_sha256"], frozen_manifest
        )
        corpus = load(root)
        candidates = _candidates(canonical)
        tasks = {t["id"]: t for t in corpus["tasks"]}
        expected = {
            (r["task_id"], r["world_id"]): r["expected_rows"]
            for r in read_json(root / "evidence/independent-expected.json")["results"]
        }
        planned = {
            _name(c, w): (c, w)
            for c in candidates
            for w in corpus["worlds"]
            if tasks[c["task_id"]]["schema"] == w["schema"]
        }
        outcomes = []
        run_digest = file_sha(destination / "manifest.json")
        for path in sorted((destination / "results").glob("*.json")):
            if path.name not in planned:
                raise ValueError("unexpected result file")
            envelope = read_json(path, 600000)
            if (
                set(envelope) != {"payload", "sha256"}
                or sha(encoded(envelope["payload"])) != envelope["sha256"]
            ):
                raise ValueError("result checksum mismatch")
            payload = envelope["payload"]
            candidate, world = planned[path.name]
            if (
                payload["run_sha256"] != run_digest
                or payload["candidate_id"] != candidate["id"]
                or payload["task_id"] != candidate["task_id"]
                or payload["world_id"] != world["id"]
                or payload["sql_sha256"] != sha(encoded(candidate["sql"]))
            ):
                raise ValueError("result identity mismatch")
            actual = payload["execution"]
            if actual.get("status") not in STATUSES | {
                "missing",
                "invalid_sql",
                "invalid_capture",
            }:
                raise ValueError("invalid result status")
            verdict = compare_result(
                tasks[candidate["task_id"]],
                expected[(candidate["task_id"], world["id"])],
                actual,
            )
            if verdict != payload["comparison"]:
                raise ValueError("stored verdict contradicts result")
            outcomes.append(payload)
        return dict(
            version=1,
            manifest=manifest,
            run_sha256=run_digest,
            canonical=canonical,
            candidates=candidates,
            outcomes=outcomes,
            planned_slots=len(candidates),
            planned_worlds=len(planned),
            completed_worlds=len(outcomes),
            complete=len(outcomes) == len(planned),
        )
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError("malformed run artifact") from error


def evaluate(root, frozen, imported, destination):
    guard()
    root, frozen, imported, destination = map(
        Path, (root, frozen, imported, destination)
    )
    frozen_manifest = freeze.verify(root, frozen)
    canonical = imports.verify(
        imported, file_sha(frozen / "manifest.json"), frozen_manifest
    )
    destination.mkdir(parents=True, exist_ok=True)
    fd = os.open(
        destination / "run.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600
    )
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError("run already has a writer") from error
        if not (destination / "manifest.json").exists():
            _initialize(root, frozen, imported, destination, canonical)
        state = read(root, destination)
        if state["manifest"]["frozen_sha256"] != file_sha(
            frozen / "manifest.json"
        ) or state["manifest"]["import_sha256"] != file_sha(imported / "manifest.json"):
            raise ValueError("resume requested with different inputs")
        done = {(p["candidate_id"], p["world_id"]) for p in state["outcomes"]}
        corpus = load(root)
        tasks = {t["id"]: t for t in corpus["tasks"]}
        expected = {
            (r["task_id"], r["world_id"]): r["expected_rows"]
            for r in read_json(root / "evidence/independent-expected.json")["results"]
        }
        for candidate in state["candidates"]:
            task = tasks[candidate["task_id"]]
            for world in (w for w in corpus["worlds"] if w["schema"] == task["schema"]):
                if (candidate["id"], world["id"]) in done:
                    continue
                guard()
                if candidate["capture_error"]:
                    actual = dict(
                        status=candidate["capture_error"],
                        columns=0,
                        rows=[],
                        error="no executable captured SQL",
                    )
                else:
                    actual = execute(
                        destination / "worlds" / (world["id"] + ".db"),
                        candidate["sql"],
                        list(corpus["schemas"][task["schema"]]["tables"]),
                    )
                verdict = compare_result(
                    task, expected[(task["id"], world["id"])], actual
                )
                payload = dict(
                    run_sha256=state["run_sha256"],
                    candidate_id=candidate["id"],
                    task_id=task["id"],
                    world_id=world["id"],
                    sql_sha256=sha(encoded(candidate["sql"])),
                    execution=actual,
                    comparison=verdict,
                )
                publish_json(
                    destination / "results" / _name(candidate, world),
                    dict(payload=payload, sha256=sha(encoded(payload))),
                )
        return read(root, destination)
    finally:
        os.close(fd)
