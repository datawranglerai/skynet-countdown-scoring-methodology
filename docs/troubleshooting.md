# Troubleshooting

Start with offline validation. It catches malformed evidence and settings before API calls:

```sh
uv run python -m skynet_countdown --input examples/stories.json --validate-only
uv run python -m skynet_countdown.benchmark --dataset examples/benchmarks/benchmark.json --validate-only
```

Validation does not test credentials, model access, or the quality of a model's judgments. Use your actual input and configuration paths when diagnosing a run.

## Startup and configuration

| Symptom | Cause and next step |
| --- | --- |
| Python syntax or version errors | The project requires Python 3.13 or newer. Run from the repository root with the environment prepared by `uv sync`. |
| `config.toml` or input file not found | Paths are relative to the current working directory. Run from the checkout root or pass explicit `--input`, `--dataset`, and `--config` paths. |
| Missing key or authentication error | Set `OPENAI_API_KEY`. If using `.env`, include `uv run --env-file .env`; the application does not load it itself. Check that the placeholder key was replaced. |
| Model unavailable or unsupported parameter | Confirm access to the configured model and support for Responses API strict structured outputs. Adjust that stage's model or reasoning setting; `reasoning_effort = "omit"` leaves out the reasoning parameter. Search also needs compatible model/tool support. |
| Unknown TOML key or invalid type | Compare with the [configuration reference](reference/configuration.md). Settings are strict: quoted numbers and quoted booleans are not converted automatically. Search settings belong only under `[scorer]`. |
| Output already exists | Choose a new filename. Existing results are preserved, and this failure occurs before paid calls. |
| Output parent directory missing | Create the parent directory or choose a file in an existing directory. The CLI does not create output directories. |

## Evidence and stage failures

| Symptom | Cause and next step |
| --- | --- |
| Input validation rejects a story | Check required fields, calendar dates, HTTP(S) URLs, blank text, and unique IDs. Place additional fields in `metadata`; do not add calculated scores as story fields. |
| The assessment says evidence is missing despite a source URL | URLs are attribution and are not fetched by default. Supply article evidence in `content` and `summary`. Optional scorer search is configured separately and is always disabled by the benchmark. |
| `Invalid structured output after ... attempt(s)` | Schema or semantic validation remained invalid after the correction limit. Inspect the stage error and audit; verify prompt/model compatibility and reproduce with the same input. `max_iterations` controls these attempts. |
| A response is incomplete | Inspect the recorded status and error details. For a token-limit failure, review that stage's `max_output_tokens`. Incomplete responses fail the stage rather than entering the schema-correction loop. |
| Refusal or incomplete web search | The stage cannot produce a usable assessment. Review the supplied evidence, request, and returned error before rerunning; the pipeline does not invent replacement ratings. |
| A run saved JSON but exited nonzero | Read `complete`, then each `stories[].error`. Later stories continue after a stage failure. Preserve the partial result and rerun corrected inputs to a new filename. |

SDK transport retries and structured-output correction attempts are separate. A network/API failure may have no response audit if no response was received. See [configuration](reference/configuration.md) before changing retry limits.

## Results that can be valid

A relevant story may score zero: relevance means the topic belongs in scope, not that it demonstrates a scored capability. A zero assessment remains visible and causes exactly zero clock movement.

A successful assessment can have no report when reports are disabled or its `raw_source_total` is below the editorial threshold. Its weighted `total_score` still contributes to the clock. A writer failure also retains the successful calculation and points, while marking the overall run incomplete.

Repeated coverage with different IDs can count the same event twice. Group events before evaluation; supplying `initial_evidence_points` does not load prior event history. For a correction to an existing ledger, rebuild the selected ledger and recalculate from its intended starting point.

## Benchmark comparisons

If a saved baseline is rejected, check dataset hash and hash basis, scorer prompt, checked source files, and active configuration. The comparison permits a different scorer model and repetition count; other active settings must match. A CLI file-byte hash differs from the in-memory serialization hash used by a direct Python call.

When deliberately changing evidence, prompts, or scoring behavior, establish a separate baseline and record why the comparison changed. Do not alter stored fingerprints to force compatibility.

Historical disagreement does not establish incorrectness. The references were produced by a model and are not reviewed gold labels. Read criterion rationales alongside differences and review the underlying evidence. Failed or missing attempts also reduce coverage; inspect that denominator before comparing agreement rates. The [benchmarking guide](benchmarking.md) explains the measures and limitations.
