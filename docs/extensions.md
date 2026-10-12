# Extending the implementation

Extend the existing input and output boundaries before adding a new orchestration layer. The scoring arithmetic, assessment schema and frozen benchmark already provide a useful verification boundary for changes. The options below are design guidance, not features implemented by the current runner.

## Optional memory with explicit context

Start by identifying what memory should contribute: a previous methodology decision, a caller-selected related event or a bounded factual chronology. Storing every previous model response does not establish that the stored information is relevant or correct.

Place memory retrieval at the orchestration boundary. The caller or an adapter should retrieve a small context snapshot, then pass it into a dedicated optional context field alongside the story. Keep the memory-free path usable without credentials or a database connection. `Story.metadata` can carry experimental context in normal evaluation, but it is unstructured and intentionally excluded by the existing benchmark; it is not a complete memory interface.

For each snapshot, record:

- The exact supplied text and its source IDs, including whether each item is source evidence or an earlier model judgement.
- The retrieval policy, selection order, context version and content hash.
- The evidence cutoff, excluding knowledge that would not have been available at the assessed event's time.
- The scope of permitted influence, so prior judgements do not substitute for evidence about the current incident.

Do not include the target case's reference ratings in context. A stored assessment can otherwise reveal the answer the benchmark is supposed to test.

Add an explicit opt-in benchmark mode for memory and preserve separate baselines. For independent cases, replay the same frozen starting context for every repetition. For an experiment that updates memory over a sequence, define the event order and restore the same initial state before every complete run. Compare both score differences and evidence quality before adopting the feature.

## LangChain integration

The present model boundary is `run_chain`, which calls the OpenAI SDK directly. A future LangChain adapter can wrap stage inputs and outputs while leaving `Assessment`, `Relevance`, `Editorial` and `calculate_score` unchanged.

Introduce that adapter when a concrete integration needs it. Verify structured-output validation, correction limits, optional search behavior, usage records and failure propagation against the existing tests. Preserve fresh case state in benchmark mode. Merely wrapping a function does not provide conversation memory, checkpoints or observability; enable each capability deliberately and document its effect on reproducibility.

Changing the model-call implementation changes benchmark fingerprints, so establish a fresh baseline after validating the adapter. Keep provider configuration at the caller boundary rather than embedding credentials or backend selection in scoring functions.

## Hosted experiment reporting

The current benchmark writes local JSON. Although LangSmith is available in the environment, the runner does not upload datasets, traces or experiments.

An optional reporting adapter could map the existing case inputs, assessments, comparison values and run metadata into hosted experiments. Reuse `compare_assessments` instead of defining a second scoring interpretation. Keep historical references out of the target model input and label agreement separately from correctness. Preserve local results and clearly record which model requests and tokens the hosted view represents, including corrections and failures.

Add explicit configuration for uploading source text and results: reporting may disclose the supplied content to another service and should not happen as a side effect of a normal local run.

## Broader evaluation coverage

The current harness evaluates the scorer against historical ratings. Expand it in small, separately interpretable increments:

| Extension | Additional fixture or evidence needed |
| --- | --- |
| Human-reviewed correctness | Reviewed ratings, reviewer identity, rubric version, rationale and adjudication policy; preserve historical references separately. |
| Relevance quality | Labelled relevant and irrelevant stories, including relevant zero-score cases; measure routing errors independently of scoring. |
| Editorial quality | Evidence-grounding and style review of the writer's four prose fields, alongside deterministic field checks. |
| Retrieval quality | Frozen source snapshots for controlled experiments, or clearly labelled live-search runs with retrieved sources retained. |
| Prompt-injection resistance | Explicit adversarial instructions embedded in input evidence, with expected adherence to the rubric and output contract. |

Stories about attacks are not automatically adversarial tests of the scorer itself. Likewise, repeated agreement with historical labels cannot replace adjudication. Review the [benchmark limitations](benchmarking.md) before deciding which extension will resolve the uncertainty that matters.
