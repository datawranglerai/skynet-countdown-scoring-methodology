# Key decisions

The implementation favors explicit inputs, small components and results that can be inspected without a running service. These decisions describe the current code and the circumstances that would justify revisiting it.

## Keep judgement and arithmetic separate

Models interpret evidence and produce criterion ratings with rationales. Python calculates weighting, classifications and symbolic clock movement. The `Assessment` schema excludes calculated fields, and the writer receives authoritative calculations rather than inventing them.

This makes arithmetic independently testable and confines model variation to evidence interpretation and prose. It does not make those judgements correct: evidence quality and rubric clarity still require review. Revisit the calculation only as an explicit methodology change, with versioned examples and updated regression coverage.

## Use explicit stages and schema boundaries

The current three model stages use a shared OpenAI Responses wrapper and a short sequential orchestrator. Pydantic validates contracts at entry and after each model response. Prompt instructions provide the evidence rules; schema validation constrains structure and cross-field consistency.

The tradeoff is less framework functionality in exchange for a direct execution path with few moving parts. A workflow framework becomes useful if branching, supported providers, tracing or checkpointing actually requires it. Preserve the existing stage contracts and scorer benchmark when introducing one; see [Extensions](extensions.md).

## Make evidence and event selection explicit

The caller collects content, groups duplicate coverage and selects one source per event. A URL is attribution, not proof that its content was read. Optional hosted search is confined to the scorer and disabled by default.

This keeps collection failures separate from scoring behavior and makes frozen benchmark inputs possible. The cost is caller responsibility for evidence completeness and event grouping. A future retrieval adapter should return explicit evidence records and provenance instead of silently changing the scorer's input.

## Start without cross-event model memory

Each story is assessed independently. Only cumulative evidence points pass between normal evaluation iterations, and those points affect deterministic clock calculations. There is no conversational history store, vector database or dependency on earlier model answers.

This limits hidden influences and makes repeated cases comparable. It also means the model cannot infer trends from earlier incidents unless the caller supplies that context. Add memory only for a concrete task, with bounded, versioned context and separate evaluation conditions.

## Preserve successful work when a later stage fails

Each story retains its relevance, assessment, calculation, report and audit records independently. A writer failure leaves an already calculated score in the cumulative total. An assessment failure never becomes a zero-score event.

Consequently, a run can contain useful results while `complete` is false. Consumers must handle partial output explicitly. Revisit this behavior only when a consuming system requires transactional publication; publication rollback should not silently discard a valid assessment.

## Use local JSON as the first persistence boundary

Both CLIs reserve a new output file before creating an API client. Existing files are not overwritten, and validation-only commands make no model calls. Configuration uses TOML, which the supported Python version reads directly.

Local artifacts keep a small project easy to run and review, but they provide neither durable job resumption nor concurrent result storage. Introduce a database or job system when operations need those capabilities, preserving the JSON contracts as an export and replay format.

## Treat historical references as comparison data

The benchmark references are model outputs, not human-approved answers. The runner separates labels from evidence and compares criterion ratings, weighted scores, consequential classification changes and repeated-run consistency. Failed attempts remain visible rather than improving apparent agreement through omission.

Agreement measures continuity, not correctness. A candidate may improve by disagreeing with the historical reference. Human-adjudicated cases require a separately versioned reference type and review provenance, rather than silently replacing historical labels.

## Compare saved runs under controlled conditions

Saved-run comparison requires matching dataset hash and hash basis, scorer prompt, relevant code contracts and active configuration apart from scorer model. Repetition counts may differ. This constrains the interpretation of changes while keeping model swaps straightforward.

A prompt, reasoning-setting or methodology experiment needs its own baseline. The report stores a wider set of fingerprints than the subset enforced by the compatibility check; a passing check is not a claim that every byte of the repository is unchanged. Source and configuration controls improve reproducibility, but do not eliminate model randomness or establish statistical significance.

See [Benchmarking](benchmarking.md) for the operating procedure and [Architecture](architecture.md) for how these decisions interact.
