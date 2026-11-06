"""Versioned imports. Every bounded model capture retains its planned denominator."""

from pathlib import Path
import re
import shutil
import tempfile
from . import freeze
from .storage import (
    file_sha,
    guard,
    parse_json,
    publish,
    publish_json,
    read_bytes,
    read_json,
    sha,
)

ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}\Z")
KINDS = {"authored_control", "reviewer_probe", "agent_capture", "safety_probe"}
LABELS = {
    "exact_gold": "sanity",
    "equivalent": "positive",
    "semantic_mutant": "negative",
    "policy": "policy",
}


def valid_sql(value):
    try:
        return (
            isinstance(value, str)
            and bool(value.strip())
            and len(value.encode("utf-8")) <= 16384
            and "\x00" not in value
        )
    except UnicodeEncodeError:
        return False


def _entries(value, known, kind):
    if (
        not isinstance(value, dict)
        or set(value) != {"version", "candidates"}
        or type(value["version"]) is not int
        or value["version"] != 1
        or not isinstance(value["candidates"], list)
        or len(value["candidates"]) > 256
    ):
        raise ValueError("invalid candidate envelope")
    candidates = []
    seen, tasks = set(), set()
    for item in value["candidates"]:
        allowed = (
            {"id", "task_id", "sql"}
            if kind == "agent_capture"
            else {"id", "task_id", "sql", "label", "label_kind", "rationale"}
        )
        if (
            not isinstance(item, dict)
            or set(item) != allowed
            or not isinstance(item["id"], str)
            or not ID.fullmatch(item["id"])
            or item["id"] in seen
            or not isinstance(item["task_id"], str)
            or item["task_id"] not in known
        ):
            raise ValueError("unknown task, duplicate/invalid ID or candidate fields")
        if kind == "agent_capture" and item["task_id"] in tasks:
            raise ValueError("duplicate model response slot")
        seen.add(item["id"])
        tasks.add(item["task_id"])
        record = dict(item, capture_error=None)
        if not valid_sql(item["sql"]):
            if kind != "agent_capture":
                raise ValueError("control SQL must be valid bounded UTF-8")
            record.update(sql=None, capture_error="invalid_sql")
        if kind != "agent_capture":
            label_kind = item["label_kind"]
            if (
                not isinstance(label_kind, str)
                or LABELS.get(label_kind) != item["label"]
                or (kind == "safety_probe") != (label_kind == "policy")
                or not isinstance(item["rationale"], str)
                or len(item["rationale"]) > 4096
            ):
                raise ValueError("invalid label/rationale")
            try:
                item["rationale"].encode("utf-8")
            except UnicodeEncodeError as error:
                raise ValueError("rationale is not UTF-8") from error
        candidates.append(record)
    return candidates


def normalize(data, manifest, kind, cohort, frozen_digest):
    if (
        not isinstance(kind, str)
        or kind not in KINDS
        or not isinstance(cohort, str)
        or not ID.fullmatch(cohort)
    ):
        raise ValueError("invalid cohort kind/id")
    if kind == "agent_capture" and cohort not in {
        s["prompt_policy"] for s in manifest["planned_slots"]
    }:
        raise ValueError("model policy not frozen")
    known = {s["task_id"] for s in manifest["planned_slots"]}
    failure, detail = None, None
    try:
        value = parse_json(data)
    except ValueError as error:
        if kind != "agent_capture":
            raise
        failure, detail = "invalid_json", str(error)[:240]
    candidates = []
    if failure is None:
        try:
            candidates = _entries(value, known, kind)
        except ValueError as error:
            if kind != "agent_capture":
                raise
            failure, detail = "invalid_envelope", str(error)[:240]
    slots = (
        [
            dict(task_id=s["task_id"], prompt_policy=cohort)
            for s in manifest["planned_slots"]
            if s["prompt_policy"] == cohort
        ]
        if kind == "agent_capture"
        else [dict(task_id=c["task_id"], candidate_id=c["id"]) for c in candidates]
    )
    return dict(
        version=1,
        kind=kind,
        cohort=cohort,
        candidates=candidates,
        slots=slots,
        capture_failure=failure,
        capture_failure_detail=detail,
        raw_sha256=sha(data),
        frozen_sha256=frozen_digest,
    )


def import_candidates(root, frozen, raw, destination, kind, cohort):
    guard()
    manifest = freeze.verify(root, frozen)
    data = read_bytes(raw)
    canonical = normalize(
        data, manifest, kind, cohort, file_sha(Path(frozen) / "manifest.json")
    )
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".import-", dir=destination.parent))
    try:
        publish(stage / "raw.json", data)
        publish_json(stage / "candidates.json", canonical)
        publish_json(
            stage / "manifest.json",
            dict(
                version=1,
                files={
                    "raw.json": file_sha(stage / "raw.json"),
                    "candidates.json": file_sha(stage / "candidates.json"),
                },
                frozen_sha256=canonical["frozen_sha256"],
            ),
        )
        stage.rename(destination)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return canonical


def verify(imported, frozen_digest, frozen_manifest):
    imported = Path(imported)
    manifest = read_json(imported / "manifest.json")
    if (
        manifest.get("version") != 1
        or manifest.get("frozen_sha256") != frozen_digest
        or set(manifest.get("files", {})) != {"raw.json", "candidates.json"}
    ):
        raise ValueError("candidate import manifest mismatch")
    for name, digest in manifest["files"].items():
        if file_sha(imported / name) != digest:
            raise ValueError("import content changed")
    canonical = read_json(imported / "candidates.json", 2 * 1024 * 1024)
    recomputed = normalize(
        read_bytes(imported / "raw.json"),
        frozen_manifest,
        canonical["kind"],
        canonical["cohort"],
        frozen_digest,
    )
    if canonical != recomputed:
        raise ValueError("canonical candidates/slots contradict raw capture")
    return canonical
