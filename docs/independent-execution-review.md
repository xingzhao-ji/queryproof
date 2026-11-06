# Independent execution/oracle checkpoint

Reviewed 2026-10-23. This covers the executor and authored oracle/control stage, not completed run persistence, reporting, blind model capture or final employer acceptance.

The initial 12-test checkpoint passed independently. Fourteen additional reviewer input/query probes exercised real worker processes: a commented write, VACUUM INTO, table-valued PRAGMA, extension loading, explicit schema access, recursive resource exhaustion, nonfinite/BLOB outputs, integer overflow, invalid strings, a valid CTE and an empty result with two columns. Launched workers were reaped and the source database hash stayed unchanged. See `evidence/independent-execution-initial.json`.

**P2 found and resolved:** an unpaired Unicode surrogate accepted by JSON raised `UnicodeEncodeError` in parent SQL admission. The builder added rejection and a regression test. The reviewer independently reran the exact input; it now yields `policy` without raising. Integer overflow producing a real SQLite value is correctly rejected for an integer task. The initial record is retained; the corrected observations and source hashes are in `evidence/independent-execution-recheck.json`. All **10 targeted executor/comparison tests passed** in 1.138 seconds, recorded in `evidence/independent-execution-checkpoint-tests.txt`.

A concurrent broad test-discovery rerun briefly included three newly authored freeze/import RED tests before that feature was implemented. Those failures are unfinished checkpoint work, not evidence of an executor regression or a passing complete product. Final full-suite validation remains required at the builder's completed checkpoint.

The executor uses a fresh worker, disposable read-only database copy, SQLite authorization, VM/result limits, CPU/output restrictions and a parent deadline. Source review found no claim of an OS sandbox; the worker runs under the user's identity, and native SQLite/Python vulnerabilities remain outside this boundary. The approximate bag comparator uses matching rather than greedy removal or numeric rounding. Row multiplicity, order, types and failed-execution status are part of correctness.

## Independent oracle and label result

The reviewer authored ordinary-Python answers and froze **144 expected task/world cells before any gold SQL existed**. The builder separately recorded authoring gold and controls before consulting those results. Afterwards, the reviewer executed the SQL directly through SQLite, without using the production executor or comparator, and compared against the frozen reference. **144/144 cells agree.** Exact input, SQL, checker and reference hashes are bound in `evidence/independent-oracle-review.json`.

All **72 authored controls** were read and adjudicated: 24 exact-gold sanity checks, 24 structurally equivalent positives and 24 semantic-negative mutations. Each negative has an actual counterexample and a contract-based reviewer reason. The anchor accepts all 24 wrong mutations; the full suite rejects all 24 across all schemas. All 24 equivalents are accepted. See `evidence/independent-control-adjudication.json` for the complete reasons and counterexample rows.

Those rates describe a deliberately designed synthetic control pool. They are not real model results, human annotation agreement, a universal equivalence proof or an estimate of production error rates. Separate reviewer-authored post-freeze probes, actual captured model outputs, fixed-denominator reporting and the completed failure workflow remain outstanding.
