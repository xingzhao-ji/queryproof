# Independent held-out and integrity review

V1 reviewed 2026-10-23 after implementation freeze. Frozen manifest SHA256: `31f8c39a507953ea54b52721c1592efa53e4771c26fb96d0644da216abde3085`. Reviewer candidates were authored afterwards at 20:14:42 UTC; their SHA256 is `0f059a22c0b08c5577520b6fce8a2b6c720679d28a7c353d163bdc20cc93b980`. Neither the corpus nor earlier oracle/adjudication bytes were changed.

The reviewer used the actual CLI to import, execute, report, compare and inspect a new 12-candidate pool. All five commands completed successfully; 72 candidate/world executions finished. Six positives use alternate constructions such as EXCEPT, INTERSECT, correlated ordered selection and a window RANGE over a unique date/ID ordering. Six negatives introduce mistakes distinct from the builder's controls. These are non-random agent-authored adversarial probes, not real model outputs or a population estimate.

| Grader | Equivalent false rejects | Semantic-negative false accepts |
| --- | ---: | ---: |
| Exact SQL string | 6/6 | 0/6 |
| Anchor world | 0/6 | 6/6 |
| Six-world suite | 0/6 | **1/6** |

The multi-world suite catches five errors involving quantity multiplication, resolved-ticket counts, the inclusive resolution cutoff, invoice/payment join inflation and integer-average truncation. The inspector exposes the actual task, SQL, world rows, expected/observed results and reason for an observed failure. Complete outputs are preserved in `evidence/independent-heldout-v1-{import,run,report,compare,inspect}.json`; inputs and authoring metadata are in `independent-heldout-v1.json` and `independent-heldout-v1-manifest.json`.

## Confirmed finite-suite false accept

`held-C07-limit100` returns paid-line SKUs with an unsupported `LIMIT 100`. Every frozen commerce world is smaller, so the suite accepts it. The reviewer constructed a constraint-valid world containing one customer, one paid order and 101 paid lines. Independent Python returns 101 SKU rows; direct SQLite execution of the candidate returns 100. This confirms the negative label without assuming author intent.

The additional world is retained in `evidence/independent-counterexample-worlds.json`; the actual expected/observed outputs and hash are in `evidence/independent-external-counterexample-v1.json`. It was **not** silently added to the frozen evaluation corpus. This is a coverage limitation, not a SQL-safety escape. The eventual README/report must retain it. A future expanded suite can address it only as a new version, with the original held-out result preserved and any follow-up described as a retest. Do not claim zero grader false accepts from the builder's easier control pool.

## P2 integrity and capture findings, pending v2 recheck

The reviewer copied the frozen directory into disposable local directories and changed only its metadata. `freeze.verify` incorrectly accepted each of:

- An empty `planned_slots` list, despite a 24-task prompt.
- A changed VM-operation limit, despite unchanged runtime source.
- Different public prompt text together with a matching replacement prompt digest.

File hashing alone does not validate these source-derived fields. The fix should rederive the planned slots, declared policy/limits and generated prompt from the bound source/corpus and reject inconsistencies. This is internal consistency checking, not a claim of signatures or resistance to an attacker rewriting every trusted source.

An entirely malformed generation JSON also refused import without preserving a cohort artifact or its 24 planned response slots. Missing/invalid SQL within a valid envelope already preserves slots, but the whole-attempt failure must also remain in the primary attempted-cohort accounting. Preserve original raw bytes and the capture error; do not repair or fabricate answers. Root and builder independently identified this same boundary.

Exact initial outcomes are in `evidence/independent-integrity-v1.json`. The builder was explicitly released to create a versioned fix only after these v1 results were recorded. Current oracle/control agreement remains valid; the corpus need not change for these fixes. Final acceptance and blind model capture await the v2 recheck.

## V2 recheck: accepted for blind capture

Frozen v2 manifest SHA256: `585e685d78b28da74ed098ce9988aeaf44aea1c9d00592b38a88d7169ae3dfcb`. Independent source inspection and actual replays confirm the P2 fixes. Empty planned slots, changed limits, changed policy name and altered prompt plus replacement digest now each fail verification. Three synthetic capture faults—malformed JSON, a non-string task ID and invalid UTF-8—retain their original raw bytes, record all **24 planned slots**, report **0/24 successes**, and keep `capture_complete=false`. The run can finish recording those failures without presenting the capture as valid. These are deliberately injected reviewer faults, not real model generations. Results are in `evidence/independent-integrity-v2.json` and the corresponding `independent-fault-*-v2-report.json` files.

The reviewer reran the unchanged held-out input through v2: **72/72 executions complete**, still 0/6 equivalent false rejects and **1/6 negative false accepts**. The retained LIMIT100 limitation was not tuned away. This v2 run is a retest of the already observed pool, not another untouched holdout. Results are in `evidence/independent-heldout-v2-report.json`.

All **31 tests passed independently in 13.760 seconds**, including actual SIGKILL/resumption, concurrent-writer refusal, corrupt-result refusal and fixed-denominator paths; log: `evidence/independent-tests-v2.txt`. All nine corpus/contract/independent-answer/adjudication inputs match v1, and the public prompt is unchanged. The source-v1 archive independently matches all **20** v1 manifest-bound files, recorded in `evidence/independent-v1-archive-check.json`, so historical results remain inspectable.

**Checkpoint decision:** v2 is accepted for root's fresh-context, prompt-only 24-task capture. No remaining blocker to that bounded next step. Final employer assessment remains pending actual capture provenance/results and final source/report review; no real model success is claimed yet. The coverage limitation above remains part of the eventual rating.
