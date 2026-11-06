# QueryProof

A text-to-SQL evaluation workbench that exposes answers which happen to work on one database. Inspect a task, import captured SQL, run it across multiple worlds, resume an interrupted run, and open a concrete counterexample with the query, data and expected/actual rows.

The project uses only Python's standard library and SQLite. It adds evaluation validity and diagnosis beyond a generic job runner: explicit task semantics, independently computed answers, adjudicated labels, deliberately misleading anchor databases and separate real-model cohorts. The approach follows established [test-suite evaluation work](https://aclanthology.org/2020.emnlp-main.29/); it is not a new equivalence algorithm.

## Corpus and evidence

- 24 authored tasks, three schemas (commerce/support/billing), 14 semantic categories; 12 development and 12 assessment tasks within known schemas.
- Six synthetic worlds per schema: simple anchor, structured edge cases, three seeded worlds and empty tables. No private applications or real customer data.
- Every output declares types, bag multiplicity, NULL behavior, order and tie breaks. Money is integer cents; the one average task uses explicit finite numeric tolerance.
- An independent agent derived ordinary-Python expected results from the natural-language contracts and rows **before seeing gold SQL**. All 144 task/world results agree with independently executed gold SQL.
- 72 authored controls: 24 exact-gold sanity checks, 24 structural equivalents and 24 semantic mutants. All labels were separately reviewed. Exact-gold checks are excluded from positive-label error rates.

The control study executes all 432 candidate/world pairs. The intentionally simple anchor accepts all 24 authored mutants; the six-world suite rejects all 24, across all schemas. All 24 equivalents pass both execution graders. Exact-string rejects all 24 equivalents. These are designed calibration cases, not representative model error rates. See [current control report](evidence/controls-report-v2.html), [retained initial report](evidence/controls-report-v1.html), and [independent adjudication](evidence/independent-control-adjudication.json).

The independent reviewer then authored 12 previously unseen probes: six equivalents and six semantic negatives. All six equivalents passed; the anchor falsely accepted all six negatives, and multi-world grading falsely accepted **one of six**. A `LIMIT 100` query passed these small worlds but returned only 100 rows on a valid separate 101-line world. The [external counterexample](evidence/independent-external-counterexample-v1.json) is preserved. This is a result for a small authored probe cohort, not a population error estimate. The corpus was not tuned after seeing that miss.

One real prompt-only Codex-agent cohort was captured in a fresh no-history context after the task/prompt/source freeze, with no grading feedback. Its **24/24 planned answers passed all six worlds** (12/12 development, 12/12 assessment; 144 successful SQL executions). The exact-string baseline accepted 0/24; single- and multi-world accepted 24/24. No model failures were invented. See the [model report](evidence/model-report-direct-v1.html), [unaltered raw answers](evidence/model-capture-direct-v1.json), [supplied task text with output-path redaction](evidence/root-capture-task.txt), and [capture metadata](evidence/root-capture-metadata.json).

Blindness was an instruction to the fresh agent, not OS-enforced isolation; only a one-time answer-file write was allowed. Exact model/version/settings, tokens and cost were unavailable and remain null. The recorded 82.05-second interval is orchestration/capture wall time, **not inference latency**. The complete provider/system prompt was not exposed. Those capture-time metadata were preserved before grading.

Authored mutants are never presented as model responses. Planned model denominators retain every task, including missing, malformed, refused, timed-out and crashed outputs. An entirely malformed bounded capture is retained as raw bytes and an `invalid_capture` cohort with all 24 unsuccessful planned slots; it cannot disappear because parsing failed. Input files must still meet the declared 1 MiB regular-file boundary. Three independently exercised malformed-capture cases each retained 0/24 rather than disappearing.

## Run locally

Requires Python 3.11+ with SQLite STRICT/window support on a POSIX platform. Actual verification currently uses Python 3.14.7/macOS; Linux execution is not claimed. No installation or network access is required.

Current verification: **31 tests passed**, independently repeated; 144 independent oracle cells agree; actual SIGKILL after two committed results resumes 18/18 while preserving their bytes. The V2 snapshot binds 20 runtime/corpus/review files. Runtime versions are recorded; execution equivalence across different Python/SQLite versions is not guaranteed.

```sh
cd queryproof
python3 -m unittest discover -s tests -v
python3 -m queryproof tasks
python3 -m queryproof task C03

# Choose a fresh output directory; existing published artifacts are never replaced.
python3 -m queryproof freeze --out /tmp/queryproof-freeze
python3 -m queryproof import-candidates \
  --freeze /tmp/queryproof-freeze --input evidence/authored-controls.json \
  --out /tmp/queryproof-import --kind authored_control --cohort authored-v1
python3 -m queryproof run --freeze /tmp/queryproof-freeze \
  --imported /tmp/queryproof-import --out /tmp/queryproof-run

# Repeating run with the same paths resumes and preserves committed result bytes.
python3 -m queryproof report /tmp/queryproof-run \
  --json-out /tmp/queryproof-report.json --html-out /tmp/queryproof-report.html
python3 -m queryproof inspect /tmp/queryproof-run C03-mutant
python3 -m queryproof compare /tmp/queryproof-run
```

Captured answers use `{"version":1,"candidates":[{"id":"C01","task_id":"C01","sql":"SELECT ..."}]}`. Import them with `--kind agent_capture --cohort direct_v1`. Use the exact frozen public prompt and record raw output plus metadata separately. The default policy has 24 planned response slots; subsets do not change its denominator. Labels are accepted only in separate control/probe cohorts. Full command help: `python3 -m queryproof --help`.

To repeat the real interruption drill, choose a fresh tag/output: `python3 scripts/verify_crash.py --freeze evidence/frozen-v2 --tag another-drill --evidence /tmp/queryproof-crash.json`. The script kills the evaluator after observing committed outcomes, resumes the same run, and verifies their exact bytes remain unchanged.

The standalone HTML uses expandable native disclosures for each candidate. No server, scripts, remote fonts or telemetry are needed. JSON reports provide overall, per-task, category and split confusion counts. Inspect returns the first failing world in the declared world order, including its row data and byte hashes; SQL errors remain distinct from semantic mismatches.

## Execution and recovery boundary

Each query runs in a short-lived subprocess against a disposable read-only copy. SQLite's [authorizer](https://www.sqlite.org/c3ref/set_authorizer.html) allows only selected tables, reads and a named deterministic function subset. Writes, ATTACH, PRAGMA, schema/extension access and multiple statements are refused. The public prompt names the supported subset.

Limits include 16 KiB SQL, 1,000 result rows, 32 columns, 16 KiB cells, 256 KiB serialized rows, approximately 200,000 VM operations and a two-second parent deadline covering preparation/iteration. The [progress handler](https://www.sqlite.org/c3ref/progress_handler.html), [SQLite limits](https://www.sqlite.org/limits.html), streaming byte accounting and child CPU/file/descriptor limits reinforce the boundary. Timeout workers are killed and reaped. Approximate bags use bounded augmenting-path matching, preserving duplicates without greedy tolerance pairing.

This is **not an OS sandbox**. The trusted Python/SQLite binary runs with the current user's OS identity; native-library vulnerabilities and attacker-controlled fixture databases/extensions are outside scope. No hard address-space isolation is claimed. Source databases and fixture schemas are trusted frozen assets; untrusted input is SQL/answer JSON. The local runtime cache has a 200 MiB allocated budget and a 2 GiB host free-space floor.

Runs bind source, corpus, prompt, imported raw bytes and materialized databases to hashes. A run-wide advisory lock prevents concurrent writers. Completed outcome files are fsynced and atomically linked without replacement. Resume checks input and outcome integrity; missing observations remain incomplete, and corrupt records fail closed. A crash can repeat unfinished computation but cannot replace a committed outcome. Hashes/checksums establish byte identity and detect accidental corruption; they do not authenticate a publisher or defeat someone able to rewrite every artifact and hash.

V1 exposed manifest-consistency and malformed-capture accounting defects. V2 derives planned slots, execution policy, limits and the public prompt from bound source/corpus, verifies review inputs, and reconstructs canonical candidates from preserved raw bytes. Earlier findings/results are retained. [source-v1.tar.gz](evidence/source-v1.tar.gz) includes every V1 manifest-bound file plus its freeze/prompt; extract into a fresh directory and run that version's CLI there when inspecting historical V1 runs. V2 source intentionally refuses a V1 run. The independent recheck and versioned artifacts distinguish fixes from untouched held-out evidence.

## What this does and does not establish

This is an AI-assisted portfolio implementation of bounded SQL evaluation infrastructure. The owner should be able to explain task ambiguity, false accepts/rejects, oracle independence, resource boundaries and recovery behavior before claiming personal mastery. It is not evidence of production ownership, human annotation agreement, broad benchmark generalization, a second independent model, GPU work or compiler construction. Worlds are not independent model samples. Hosted generation reproducibility, provider settings, inference latency, tokens and costs remain unavailable unless actually provided; replay of preserved bytes is the reproducible part.

See [design](docs/design.md), [task contracts](docs/task-contract.md), [independent automated review](docs/independent-employer-review.md), and [public export provenance](PUBLICATION.md) for scope and limitations.
