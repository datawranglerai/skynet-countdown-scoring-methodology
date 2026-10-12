# Configuration

Both CLIs load `config.toml` by default. Select another file with `--config path/to/settings.toml`. Python's standard TOML parser reads it, and `skynet_countdown/config.py` validates it. Every setting is optional; unknown keys, invalid types, and invalid values fail before a live run starts.

API credentials come from the environment. There is no API-key field in TOML, and the application does not load `.env` itself. Use `uv run --env-file .env ...` when keeping local credentials there.

## Supplied configuration and built-in defaults

The tables below describe **built-in fallback values** from `Config()` in `config.py`. They apply when a setting is omitted. The CLIs load `config.toml`, whose supplied values take precedence:

| Setting | Supplied `config.toml` | Built-in fallback |
| --- | --- | --- |
| Each stage's `model` | `gpt-5.4-mini` | `gpt-5.4` |
| Each stage's `reasoning_effort` | `medium` | `high` |
| `scorer.max_tool_calls` | `3` | `5` |

The supplied scoring, clock and relevance/report thresholds still match the published methodology. Inspect your selected TOML file before a run; the result records the resolved settings. A Python integration using `Config()` directly receives the built-in defaults instead of these file overrides.

## Pipeline and transport

| Setting | Default | Meaning and constraints |
| --- | --- | --- |
| `minimum_relevance_score` | `2` | Integer 1–10. A story advances only if its relevance flag is true and its score meets this threshold. The rubric separately requires scores 1–2 to have a false flag. |
| `minimum_report_score` | `2` | Nonnegative integer threshold on `raw_source_total`. Controls writing only; successful assessments still contribute their weighted points. |
| `write_reports` | `true` | Boolean switch for the editorial stage. |
| `request_timeout_seconds` | `180.0` | Positive finite timeout passed to the API client. |
| `api_max_retries` | `2` | Nonnegative integer SDK retry limit for transport/API failures. |

The CLIs construct the client with these transport settings. Integrations calling `evaluate()` or `evaluate_benchmark()` directly own the client and its timeout/retry configuration.

## Per-stage model settings

The `[relevance]`, `[scorer]`, and `[writer]` tables each accept these settings:

| Setting | Default | Meaning and constraints |
| --- | --- | --- |
| `model` | `"gpt-5.4"` | Nonblank model identifier. Access and API compatibility are checked by the provider during a live request. |
| `reasoning_effort` | `"high"` | One of `omit`, `none`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max`. Accepted values depend on the chosen model. |
| `max_iterations` | `2` | Positive integer: total structured-output attempts, including the first request. |
| `max_output_tokens` | `8192` | Positive integer output-token limit passed to each request. |

Set `reasoning_effort = "omit"` to omit the API reasoning parameter. This differs from sending `"none"`. Choose a model that supports the Responses API and strict JSON-schema outputs; setting an arbitrary model name does not establish compatibility.

Only `[scorer]` accepts retrieval settings:

| Setting | Default | Meaning and constraints |
| --- | --- | --- |
| `web_search` | `false` | Enable hosted web search for checking the supplied story. Requires model/tool support. |
| `web_search_context_size` | `"medium"` | One of `low`, `medium`, `high`. |
| `max_tool_calls` | `5` | Positive integer hosted tool-call limit per scorer request. |

Relevance and writing always use supplied inputs. Search does not turn the pipeline into a story collector.

### Three different limits

`max_iterations` allows correction after schema or Pydantic validation failures. The failed JSON and validation errors are added to the next request. Refusals, incomplete responses, and incomplete searches fail the stage instead of entering this correction loop.

`api_max_retries` belongs to the SDK's transport behavior. `max_tool_calls` bounds hosted tools within each request, including a correction request. Increasing one limit does not increase the others, and a single assessment may involve several billable requests.

## Scoring and clock

| Setting | Default | Meaning and constraints |
| --- | --- | --- |
| `scoring.trifecta_points` | `[0, 1, 3, 7]` | Four nonnegative integer entries indexed by active Trifecta checks. Must start at zero and never decrease. |
| `scoring.severity_thresholds.CANARY` | `1` | Inclusive lower bound; must equal 1. |
| `scoring.severity_thresholds.NOTABLE` | `3` | Inclusive lower bound. |
| `scoring.severity_thresholds.SIGNIFICANT` | `5` | Inclusive lower bound. |
| `scoring.severity_thresholds.CRITICAL` | `7` | Inclusive lower bound. |
| `scoring.severity_thresholds.EXISTENTIAL` | `13` | Inclusive lower bound. All severity thresholds must strictly increase. |
| `clock.initial_seconds` | `900.0` | Positive finite starting symbolic window: 15 minutes. |
| `clock.half_scale_points` | `1000.0` | Positive finite evidence points required to halve the remaining window. |
| `clock.initial_evidence_points` | `0` | Nonnegative integer at most `2**53 - 1`. Supplies a prior total, not event history or deduplication. |

Zero always means `NO_MOVEMENT`. The maximum weighted score is `trifecta_points[3] + 10`. See the [methodology](../methodology.md) before changing calibration or thresholds.

## Published profile and benchmark overrides

Results report `methodology_profile: "published"` when the scoring table, severity thresholds, initial window, half-scale, and relevance/report thresholds match the defaults. Changes to these produce `"custom"`. Model settings, disabling reports, and supplying prior evidence do not change the profile.

The benchmark forces `scorer.web_search = false`, `write_reports = false`, and `clock.initial_evidence_points = 0`. It bypasses relevance and writing and records both supplied and effective configuration. `--model` overrides only the scorer model. See [benchmarking](../benchmarking.md) for the settings that must match a saved baseline.
