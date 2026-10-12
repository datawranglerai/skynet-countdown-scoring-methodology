# Python API

The package can be called directly from a checkout. Public entry points accept validated Pydantic objects and an injected OpenAI client; calculation and comparison functions need no network access. See [Data contracts](data-contracts.md) for field definitions and [Configuration](configuration.md) for defaults.

## Load configuration and inputs

```python
from pathlib import Path

from skynet_countdown.config import load_config
from skynet_countdown.models import Dataset

config = load_config("config.toml")
dataset = Dataset.model_validate_json(
    Path("examples/stories.json").read_text(encoding="utf-8-sig")
)
```

`load_config(path: str | Path) -> Config` reads TOML and validates it. `Config()` constructs published defaults without reading a file. These models reject unknown fields and invalid values. For date-bearing JSON, use `model_validate_json` as shown; strict Python-mode validation expects Python date objects rather than arbitrary date strings.

## Evaluate stories

```python
def evaluate(
    dataset: Dataset,
    config: Config,
    *,
    client: OpenAI,
) -> EvaluationResult: ...
```

```python
from openai import OpenAI

from skynet_countdown.pipeline import evaluate

with OpenAI(
    timeout=config.request_timeout_seconds,
    max_retries=config.api_max_retries,
) as client:
    result = evaluate(dataset, config, client=client)

with Path("results-api.json").open("x", encoding="utf-8") as output:
    output.write(result.model_dump_json(indent=2) + "\n")

print(result.complete, result.cumulative_points)
```

This example makes paid model calls and expects credentials in the environment. The caller owns the client, its lifecycle, transport retries and timeout; passing `Config` does not reconfigure an existing client. For pre-reservation of an output path before model calls, use the CLI or reserve the file before invoking `evaluate`.

`evaluate` revalidates the dataset and configuration, orders stories by date and ID, and returns an `EvaluationResult`. Expected per-story model and calculation failures are recorded in `StoryResult.error`; inspect `complete` and each story's available fields. Invalid initial configuration can raise before processing starts. See [Architecture](../architecture.md) for partial-result and cumulative-total semantics.

## Calculate or compare without model calls

```python
def calculate_score(
    assessment: Assessment,
    scoring: ScoringConfig,
    clock: ClockConfig,
    *,
    cumulative_points: int,
) -> CalculatedScore: ...

def compare_assessments(
    reference: Assessment,
    actual: Assessment,
    config: Config,
) -> dict[str, Any]: ...
```

Import these functions from `skynet_countdown.scoring` and `skynet_countdown.benchmark`, respectively. `calculate_score` validates ratings and settings, then returns the raw sum, weighted total, severity and clock movement. Supply the cumulative baseline explicitly.

`compare_assessments` calculates both assessments from zero under the same settings. It returns per-criterion deltas, both calculations, weighted-score differences and changes to severity, full Trifecta and leading-indicator status. Positive deltas mean higher candidate ratings. Its historical `error` field names describe differences, not proven mistakes.

The scoring module also exposes `remaining_seconds(points, config)`, `gap_closed_percent(score, config)`, `evidence_pressure_percent(points, config)` and the three presentation helpers `format_remaining_time`, `format_movement_seconds` and `format_evidence_pressure`.

## Evaluate a benchmark

```python
def evaluate_benchmark(
    dataset: BenchmarkDataset,
    config: Config,
    *,
    client: OpenAI,
    repetitions: int = 1,
    dataset_sha256: str | None = None,
    baseline: dict[str, Any] | None = None,
) -> dict[str, Any]: ...
```

```python
from hashlib import sha256

from skynet_countdown.benchmark import BenchmarkDataset, evaluate_benchmark

source = Path("examples/benchmarks/benchmark.json").read_bytes()
benchmark = BenchmarkDataset.model_validate_json(source.decode("utf-8-sig"))

with OpenAI(
    timeout=config.request_timeout_seconds,
    max_retries=config.api_max_retries,
) as client:
    report = evaluate_benchmark(
        benchmark,
        config,
        client=client,
        repetitions=3,
        dataset_sha256=sha256(source).hexdigest(),
    )

print(report["complete"], report["summary"]["successful_assessments"])
```

This also makes paid calls. The runner copies and validates configuration, disables search and writing, and resets the clock baseline without mutating the supplied `Config`. Every case and repetition begins a fresh scorer request. Reference assessments, provenance, tags and story metadata are excluded from its input.

Return values are JSON-compatible dictionaries; serialize with `json.dump(..., allow_nan=False)` if needed. Passing `dataset_sha256` records a file-byte fingerprint; omitting it hashes serialized validated data instead. The CLI uses file bytes, so use the same basis for compatible saved-run comparisons. Supply `baseline=json.loads(...)` to compare a prior report; incompatible evidence, instructions, contracts or active settings fail before model calls.

## Lower-level chain boundary

`llm.run_chain(client, *, instructions, payload, output_type, settings, audit)` returns an instance of the requested Pydantic model and appends response records to the supplied `list[AgentRun]`. `settings` is a `ChainConfig` or `ScorerConfig`; only the latter can enable search. `ChainError` reports unusable model output. Prefer the runners unless an integration specifically needs this stage boundary.
