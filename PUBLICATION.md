# Public export provenance

The current runtime, tests, synthetic corpus, task contracts, independent expected answers, adjudication and 20 frozen v2 inputs retain their accepted bytes. The two historical source archives retain their original contents. The raw 24-answer model capture and numerical results are unchanged.

Public documentation omits private job-selection discussion and internal workflow files. Historical logs, command records and the archived task text replace the private home-directory prefix with `$HOME`; the task prompt itself is unchanged. Original embedded hashes still describe the original records. They are not hashes of these redacted public copies. `publication-transformations.json` records both identities. In particular, the original task-text hash in capture metadata differs from the redacted task file; no new model generation or inference telemetry is claimed.

The larger private replay bundle is omitted. The included v1/v2 source archives contain frozen runtime/corpus/review inputs, not an installed environment or private application documents. Some historical review scripts expect the original run cache or exact unredacted records; they are retained for inspection, not advertised as new standalone checks. Follow the README workflow and unit tests to create new runs without overwriting historical evidence.

No private applications, real customer datasets, model weights, credentials or dependency environments are distributed. The project is AI-assisted, and automated artifact review does not establish personal mastery. No project license grant has been invented.
