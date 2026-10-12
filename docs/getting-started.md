# Getting started

Run the pipeline from the repository checkout with Python 3.13 or newer and `uv`. It accepts stories you have already collected, evaluates their evidence, and writes one local JSON result. It does not collect articles or publish results to another service.

## Validate without calling a model

Run these commands from the repository root:

```sh
uv sync
uv run python -m skynet_countdown --input examples/stories.json --validate-only
```

The checked-in example contains two explicitly fictional stories. Use it to understand the input contract, not as a set of real incident assessments. Validation checks the JSON, unique story IDs, and `config.toml`; it needs no API key and makes no model requests.

You can choose another settings file with `--config path/to/settings.toml`. Omitted settings use the defaults described in the [configuration reference](reference/configuration.md).

## Supply your evidence

Create a UTF-8 JSON object with a `stories` array. This is a minimal fictional example:

```json
{
  "stories": [
    {
      "id": "fictional-support-agent",
      "title": "A fictional support agent receives production access",
      "source_url": "https://example.com/fictional-support-agent",
      "published_date": "2026-10-01",
      "summary": "The fictional agent reads customer emails and updates records after human approval.",
      "content": "FICTIONAL EXAMPLE. Every proposed record update requires a human to approve it before execution."
    }
  ]
}
```

Use one stable ID and one selected source for each distinct event. Group duplicate coverage before running the pipeline: unique IDs prevent duplicate keys, but cannot detect two articles describing the same event. Stories are evaluated by publication date, then ID.

A source URL is attribution; the default pipeline does not fetch it. Provide the article evidence in `summary` and, preferably, `content`. A headline alone rarely establishes permissions, deployment conditions, or meaningful human oversight. See the [data contracts](reference/data-contracts.md) for optional fields and validation rules.

## Run a live evaluation

Copy `.env.example` to `.env` and replace its placeholder with your `OPENAI_API_KEY`, or set that environment variable in your shell. The application does not automatically load `.env`; the following command asks `uv` to load it:

```sh
uv run --env-file .env python -m skynet_countdown --input examples/stories.json --output results.json
```

!!! note "Live requests"
    Evaluation sends the supplied story fields to the model provider and incurs API charges. The supplied `config.toml` uses `gpt-5.4-mini` with medium reasoning effort. Confirm model access and adjust the per-stage settings when needed. Omitted settings use the separate built-in defaults listed in the [configuration reference](reference/configuration.md).

Choose a new output filename each time. The parent directory must already exist, and the CLI never overwrites an existing file. It reserves the output path before making paid calls.

## Read the result

Open `results.json` in your editor, or format it in the terminal:

```sh
uv run python -m json.tool results.json
```

Check `complete` first, then inspect each story's `status` and `error`. The result retains the supplied evidence, relevance decision, criterion ratings and rationales, deterministic calculation, optional report, and model-response audit records.

`calculation.total_score` is the published weighted score. `calculation.raw_source_total` is the unweighted sum used to decide whether to write a report. A valid zero-score assessment remains in the result; it does not move the symbolic clock. Reports can be disabled with `write_reports = false` without discarding successful assessments.

If a stage fails, later stories still run, the JSON preserves partial results, and the command exits with a nonzero status. Review errors before using its aggregate total. See [troubleshooting](troubleshooting.md) for recovery.

## Validate the benchmark

The evaluation harness uses frozen evidence and historical model ratings:

```sh
uv run python -m skynet_countdown.benchmark --dataset examples/benchmarks/benchmark.json --validate-only
```

This validates the 40-case dataset without API calls. Historical ratings are unreviewed reference outputs, so agreement measures continuity rather than correctness. Continue to the [benchmarking guide](benchmarking.md) to record a local baseline, repeat assessments, and compare a candidate model under controlled settings.
