# Component map

The package separates evidence interpretation from calculation and presentation. Its modules are small enough to follow directly; the table shows where an input becomes a judgement, a deterministic result or an operational record.

| Component | Responsibility | Inputs and outputs |
| --- | --- | --- |
| `skynet_countdown/__main__.py` | Main command-line boundary | Reads story JSON and TOML, constructs a client, calls `evaluate`, writes a new result file and returns an exit status. |
| `config.py` | Validated runtime and methodology settings | `load_config` reads TOML into `Config`; nested settings cover stages, scoring thresholds and the symbolic clock. |
| `models.py` | Shared data contracts | Validates stories, model judgements, calculated values, reports and run records. Unknown fields and incompatible types are rejected. |
| `llm.py` | One structured model stage | `run_chain` combines instructions, evidence and an output schema, then returns a validated model or raises an error. |
| `pipeline.py` | Normal evaluation orchestration | `evaluate` orders a `Dataset`, runs the stage sequence and returns an `EvaluationResult` with partial successes preserved. |
| `scoring.py` | Deterministic calculation and display | Converts `Assessment` ratings and configured constants into `CalculatedScore`, clock values and formatted labels. No API client is needed. |
| `benchmark.py` | Isolated scorer comparison and CLI | Validates benchmark cases, repeats scoring, compares assessments and optionally compares a compatible saved report. |
| `prompts/*.txt` | Stage-specific interpretation rules | Defines relevance, criterion evidence anchors and editorial voice. The runners hash the packaged prompts. |

## Contracts at each boundary

`Story` carries a stable event ID, title, source URL, date and summary, with optional content and metadata. `Dataset` rejects duplicate IDs. Supplying article text is the caller's responsibility; the normal dataset permits sparse evidence, while `BenchmarkCase` requires frozen content.

`Relevance` keeps the routing judgement separate from the scoring rubric. Its validator rejects a positive relevance flag with a score of 1 or 2. `Assessment` permits only the eight criterion ratings and explanatory fields: it cannot contain an invented total or clock value. The leading-indicator flag and note must agree.

`CalculatedScore` is application output. It records both the raw sum and published weighted total, the classification and before/after clock values. `Editorial` is the writer's four-field response; `Report` adds the deterministic fields after validation. `StoryResult` retains whatever completed successfully at each stage.

Full field definitions and accepted JSON shapes are in [Data contracts](reference/data-contracts.md).

## Structured requests and corrections

`run_chain` requests strict JSON Schema output derived from the chosen Pydantic model and validates the returned JSON locally. These are complementary checks: model-side schema restrictions control structure, while Python validators enforce rules such as coherent relevance flags or headline length.

If a completed response fails validation, another attempt includes that response and a bounded list of validation errors. `max_iterations` limits these structured-output attempts. Refusals, incomplete responses and failed hosted searches raise `ChainError`; they do not create a substitute assessment. Transport errors and retries belong to the injected SDK client, so `api_max_retries` and `max_iterations` measure different things.

For each returned response, an `AgentRun` records the response ID, returned model name, status, available token usage, citations and search calls. A transport failure before any response may therefore have an error record without an `AgentRun`.

## How the two runners share behavior

Normal evaluation and benchmarking both use `run_chain`, `Assessment`, the scorer prompt and `calculate_score`. This avoids a separate interpretation of the scoring rules in the benchmark. The normal pipeline also runs relevance and optional writing; the benchmark deliberately isolates the scorer and excludes story metadata to keep historical labels out of its evidence payload.

`compare_assessments` recomputes reference and candidate scores under the same configured rules. `summarize` reports agreement conditional on successful assessments and exposes failure and missing-attempt coverage separately. Saved-run comparisons recompute values from recorded assessments rather than trusting stored aggregate metrics.

## Supporting repository files

`config.toml` is the editable runtime configuration. `examples/stories.json` demonstrates normal inputs with fictional stories; `examples/benchmarks/benchmark.json` contains the frozen historical comparison set. Tests cover contract validation, exhaustive rating arithmetic, stage failure handling, CLI output protection and benchmark isolation.

The [Python API](reference/python-api.md) provides integration entry points. [Development](development.md) covers verification, and [Extensions](extensions.md) explains where optional memory or hosted experiment reporting can fit without changing the scoring core.
