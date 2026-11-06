"""Freeze exact task/data/implementation bytes before candidate capture."""

from pathlib import Path
import shutil
import tempfile
from .corpus import load
from .storage import encoded, file_sha, guard, publish, publish_json, read_json, sha
from .worker import FUNCTIONS

LIMITS = dict(
    sql_bytes=16384,
    rows=1000,
    columns=32,
    result_bytes=262144,
    cell_bytes=16384,
    vm_operations=200000,
    wall_seconds=2,
    approximate_bag_rows=200,
)


def derived(corpus, prompt):
    return dict(
        version=1,
        policy="queryproof-v2",
        prompt_sha256=sha(prompt),
        planned_slots=[
            dict(task_id=t["id"], prompt_policy="direct_v1") for t in corpus["tasks"]
        ],
        limits=LIMITS,
        expected_cells=144,
    )


def source_paths(root):
    return sorted(
        str(p.relative_to(root))
        for pattern in ("queryproof/*.py", "corpus/*.json", "docs/task-contract.md")
        for p in root.glob(pattern)
    )


def public_prompt(root):
    data = load(root)
    text = [
        'Write one SQLite SELECT/WITH query for each of the following 24 tasks. Do not run queries or inspect any files, worlds, gold answers or tools. Return one JSON object only: {"version":1,"candidates":[{"id":"C01","task_id":"C01","sql":"SELECT ..."},...]}. Use each task ID once. No markdown, explanations or invented metadata.',
        "Only these deterministic SQL functions are supported: "
        + ", ".join(sorted(FUNCTIONS))
        + ". SELECT/CTEs, joins, EXISTS, CASE, set operations and windows are allowed. One statement, <=16 KiB; no PRAGMA/schema access/extensions/writes. SQLite STRICT types; dates are canonical valid YYYY-MM-DD; integer currency cents. Column aliases do not matter, position and declared type do. Unordered results are bags retaining duplicates; ordered results must follow every tie breaker. Finite real results use absolute/relative tolerance 1e-9. All output columns non-NULL. IDs positive; all FKs valid. Payments and events occur on/after parent dates. Resolved dates are on/after opening. Empty tables/zero-child entities, repeated dates, NULLs and overpayments are possible.",
    ]
    for name, schema in data["schemas"].items():
        text.extend(["SCHEMA " + name, schema["ddl"]])
    for task in data["tasks"]:
        text.append(
            task["id"]
            + " ["
            + task["schema"]
            + "]: "
            + task["prompt"]
            + " Output: "
            + task["semantics"]
        )
    return "\n\n".join(text) + "\n"


def validated_inputs(root, oracle_review):
    review = read_json(oracle_review, 2 * 1024 * 1024)
    required = [
        "corpus/tasks.json",
        "corpus/schemas.json",
        "corpus/worlds.json",
        "corpus/oracles.json",
        "docs/task-contract.md",
        "evidence/independent-expected.json",
    ]
    if review.get("status") != "passed" or review.get("cells") != 144:
        raise ValueError("144-cell independent oracle agreement required")
    for path in required:
        if review.get("input_sha256", {}).get(path) != file_sha(root / path):
            raise ValueError("oracle agreement input hash mismatch: " + path)
    expected = read_json(root / "evidence/independent-expected.json")
    corpus = load(root)
    cells = {
        (t["id"], w["id"])
        for t in corpus["tasks"]
        for w in corpus["worlds"]
        if t["schema"] == w["schema"]
    }
    observed = [(r["task_id"], r["world_id"]) for r in expected["results"]]
    if len(observed) != 144 or set(observed) != cells:
        raise ValueError("independent expected cells incomplete or duplicated")
    labels_path = "evidence/independent-control-adjudication.json"
    labels = read_json(root / labels_path, 2 * 1024 * 1024)
    if (
        labels.get("status") != "passed"
        or labels.get("candidate_count") != 72
        or labels.get("sql_sha256", {}).get("corpus/controls.json")
        != file_sha(root / "corpus/controls.json")
        or not all(a.get("label_supported") for a in labels.get("adjudications", []))
        or len(labels.get("adjudications", [])) != 72
    ):
        raise ValueError("72 independently adjudicated authored controls required")
    for path in required:
        if labels.get("input_sha256", {}).get(path) != file_sha(root / path):
            raise ValueError("control adjudication input hash mismatch: " + path)
    approved = {a["candidate_id"]: a for a in labels["adjudications"]}
    for candidate in corpus["controls"]:
        item = approved.get(candidate["id"])
        if item is None or any(
            item[k] != candidate[k] for k in ("task_id", "label", "label_kind")
        ):
            raise ValueError("control adjudication identity/label mismatch")
    return corpus


def create(root, destination, oracle_review):
    guard()
    root, destination, oracle_review = (
        Path(root).resolve(),
        Path(destination),
        Path(oracle_review).resolve(),
    )
    if destination.exists():
        raise FileExistsError(destination)
    corpus = validated_inputs(root, oracle_review)
    labels_path = "evidence/independent-control-adjudication.json"
    paths = source_paths(root) + [
        str(oracle_review.relative_to(root)),
        "evidence/independent-expected.json",
        labels_path,
    ]
    prompt = public_prompt(root).encode()
    manifest = dict(
        **derived(corpus, prompt),
        files={p: file_sha(root / p) for p in paths},
        source_paths=source_paths(root),
        oracle_review=str(oracle_review.relative_to(root)),
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".freeze-", dir=destination.parent))
    try:
        publish(stage / "public-prompt.txt", prompt)
        publish_json(stage / "manifest.json", manifest)
        # rename cannot replace a nonempty existing directory; callers use unique destinations.
        stage.rename(destination)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return manifest


def verify(root, frozen):
    root, frozen = Path(root).resolve(), Path(frozen)
    manifest = read_json(frozen / "manifest.json")
    if (
        not isinstance(manifest, dict)
        or manifest.get("source_paths") != source_paths(root)
        or not isinstance(manifest.get("oracle_review"), str)
    ):
        raise ValueError("frozen source inventory mismatch")
    review = (root / manifest["oracle_review"]).resolve()
    if not review.is_relative_to(root):
        raise ValueError("oracle review outside project")
    corpus = validated_inputs(root, review)
    expected = derived(corpus, public_prompt(root).encode())
    if set(manifest) != set(expected) | {
        "files",
        "source_paths",
        "oracle_review",
    } or any(encoded(manifest.get(k)) != encoded(v) for k, v in expected.items()):
        raise ValueError(
            "frozen policy/slots/limits/prompt differs from bound implementation"
        )
    permitted = set(source_paths(root)) | {
        "evidence/independent-expected.json",
        "evidence/independent-control-adjudication.json",
        manifest.get("oracle_review", ""),
    }
    if set(manifest["files"]) != permitted:
        raise ValueError("frozen file inventory mismatch")
    for relative, digest in manifest["files"].items():
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or file_sha(path) != digest:
            raise ValueError("frozen input/source changed: " + relative)
    if file_sha(frozen / "public-prompt.txt") != manifest["prompt_sha256"]:
        raise ValueError("frozen prompt changed")
    return manifest
