# Independent automated technical review — QueryProof

Reviewed 2026-10-23 by a separate AI agent. Accept the implemented bounded evaluation workbench. This technical artifact review is not human employer endorsement, production ownership, personal mastery or proof of universal SQL equivalence.

The strongest evidence is an independently checked answer oracle, explicit semantic labels, measured grader mistakes, preserved real generated SQL and concrete counterexample diagnosis. These mechanisms supply the technical evidence discussed below.

## What was independently verified

The final check in [independent-final-review.json](../evidence/independent-final-review.json), produced by [independent-final-check.py](../evidence/independent-final-check.py), verifies frozen v2 manifest `585e685d78b28da74ed098ce9988aeaf44aea1c9d00592b38a88d7169ae3dfcb`. All 20 bound source/corpus/review files match the current source and source-v2 archive. Its public prompt remains `13fc1e94f961cb0f25857e2614c7e9b477d62a908062228eec7b07eeace986db`; tasks and worlds were not tuned after the reviewer miss or real capture.

The 5,442-byte real capture matches SHA256 `a9a215714428aa6d4fd53c4b0aa92d5423ce7539f0866cea067a6bcce48ff7e1`, its import preserves the exact bytes, and it covers each of 24 planned tasks once. The archived root task ends with the exact frozen public prompt. A fresh no-history candidate agent was instructed to use only that task and perform one output write. The record does not prove OS isolation or export the provider's complete system context. Unknown model/version/settings, token usage and cost remain null; 82.047629 seconds is an orchestration interval, not inference latency.

I read all 24 SQL answers against their natural-language contracts. In particular, outer aggregation retains empty parents; anti-existence avoids nullable `NOT IN`; tie-breaking uses both date and ID; signed invoice balances are aggregated before account filtering; and invoice-weighted averages and cumulative payment windows match the requested units. I then independently executed every answer on fresh SQLite databases and compared results with my ordinary-Python reference authored before seeing gold SQL. **All 144 cells agree**, including output widths, types, bags and ordering. Stored worker results also agree, and regenerating the summary reproduces the published JSON exactly.

| Cohort | Observed result | Interpretation |
| --- | --- | --- |
| Real prompt-only capture | 24/24 planned answers pass; development 12/12, assessment 12/12; 144 `ok` executions | One small capture over known schemas. Exact-string accepts 0/24; anchor and multi-world accept 24/24. There are no real-model failures in this sample. |
| Authored calibration | 24 exact-gold sanity checks; 24 equivalents accepted; all 24 mutants rejected by multi-world but accepted by anchor | Designed controls, with independently reasoned labels and oracle agreement; not a model error estimate. Sanity checks stay outside positive-label rates. |
| Independent post-freeze probes | All 6 equivalents accepted; anchor accepts all 6 negatives; multi-world accepts 1/6 negatives | The retained `LIMIT 100` false accept demonstrates finite-suite weakness. A separate valid 101-line world returns 100 rather than 101 rows. |
| Synthetic malformed-capture faults | Malformed JSON, non-string task ID and invalid UTF-8 each preserve raw bytes and all 24 unsuccessful slots | Reviewer-injected faults, not three model attempts. Completed failure recording does not become a valid capture. |

The v2 reviewer-probe replay is a retest of the already observed v1 pool, not a second untouched holdout. No statistical population claim is supported by six authored negatives, and 144 task/world executions are not 144 independent model samples.

## Six acceptance gates

| Gate | Result and boundary |
| --- | --- |
| Frozen task contract | Passed: 24 tasks, three schemas, 14 categories, precise types/NULL/bag/order/tie/date semantics. The 12 assessment tasks share known schemas with development tasks. |
| Independent oracle | Passed: pre-gold Python expectations and all 144 gold cells agree; 72 labels were separately adjudicated. These are agent-authored/reviewed labels, not human agreement measurements. |
| Discriminating worlds | Passed with an explicit limitation: multiple semantic failures across all schemas are caught, while the independent LIMIT100 miss remains visible. Finite testing does not prove universal equivalence. |
| Actual preserved generation | Passed: one unedited, instruction-restricted capture after freeze, all 24 planned slots retained. No second independent model, hosted-inference reproducibility or provider telemetry is claimed. |
| Bounded execution and recovery | Passed for the declared local trust model: actual subprocess/SQLite authorizer, read-only copies, row/byte/VM/deadline controls, reaped timeout children, immutable committed outcomes and resume. No OS sandbox or arbitrary native-code security claim. |
| Useful reviewer workflow | Passed: task/import/run/report/inspect/compare operate on real artifacts. Final recheck opened `held-C01-unit-only` on `commerce-edge`, independently confirmed differing expected/actual rows, and compared separate cohorts under the same freeze. HTML exposes 24 candidate disclosures and the model denominator. No browser visual/accessibility test was performed. |

At the accepted v2 checkpoint I independently ran all **31 tests** in 13.760 seconds, including real SIGKILL/resumption, concurrent-writer refusal and corrupt-result refusal. The final capture check verifies that the bound runtime source has remained unchanged since that checkpoint. The owner's separately preserved crash record shows actual exit `-9` after two committed outcomes, incomplete 2/18 coverage, then 18/18 on resume with prior result bytes preserved; I inspected that record, rather than claiming to have performed that additional owner drill. Earlier Unicode, derived-manifest and whole-capture denominator defects have retained pre-fix evidence and independently checked v2 corrections.

**Remaining material limitation:** multi-world grading has a demonstrated false accept (1/6 reviewer negatives). The README now discloses it beside the real 24/24 result. Keep both facts together; expanding a future version should preserve the original frozen study. This accepted project is AI-assisted evidence to understand and extend, not a claim that the user personally authored or mastered every component.
