# Skynet Countdown: scoring methodology

[![PyPI version](https://img.shields.io/pypi/v/skynet-countdown-scoring-methodology.svg)](https://pypi.org/project/skynet-countdown-scoring-methodology/)

This open-source Python companion to [Skynet Countdown](https://skynetcountdown.org) reproduces the published scoring calculation locally from stories you've already collected. You can inspect the model's evidence judgements.

This project starts after collection and scraping. It does not discover stories, scrape articles, reconcile duplicate events, manage assessment history, allocate CVE identifiers, or publish data to external sources. It writes one local JSON result.

The index is editorial: its clock is symbolic, not a forecast or a probability of catastrophe.

[METHODOLOGY.md](METHODOLOGY.md) is the scoring authority: methodology v1.0, with calibration effective **7 October 2026**. Python derives the published totals and clock values from the component ratings.

## Quick start

Use Python 3.13 or newer and [uv](https://docs.astral.sh/uv/). Run commands from the repository root:

```sh
uv sync
uv run python -m skynet_countdown --input examples/stories.json --validate-only
```

Validation checks the dataset and configuration without making API calls. The example stories are explicitly fictional and demonstrate the input format, not real incident assessments.

Copy `.env.example` to `.env` and set `OPENAI_API_KEY`. Then run:

```sh
uv run --env-file .env python -m skynet_countdown --input examples/stories.json --output results.json
```

Evaluation sends supplied story fields to OpenAI and incurs API charges. The default model is `gpt-5.4` with high reasoning effort. You can change both settings in `config.toml`; choose a model you can access. Existing environment variables work too: the application itself does not load `.env`.

The output path must be new and its parent directory must exist. Existing files are never overwritten. Use `--config path/to/config.toml` to select another configuration.

Its only runtime dependencies are the OpenAI SDK and Pydantic.

### Install from PyPI

Once the first release is published, you can install it in a Python 3.13+ virtual environment:

```sh
python -m pip install skynet-countdown-scoring-methodology
skynet-countdown --input stories.json --config config.toml --validate-only
```

Supply your own `stories.json` and `config.toml`. Copy the repository's [`config.toml`](https://github.com/datawranglerai/skynet-countdown-scoring-methodology/blob/main/config.toml), or create an empty TOML file to use the defaults. Set `OPENAI_API_KEY` and replace `--validate-only` with `--output results.json` to evaluate stories. You can also run the installed package with `python -m skynet_countdown`.

Maintainers can find release setup and versioning instructions in [CONTRIBUTING.md](CONTRIBUTING.md#publishing-releases).

## Supply stories

The input is a UTF-8 JSON object containing a `stories` array:

```json
{
  "stories": [
    {
      "id": "my-event-001",
      "title": "A fictional AI deployment",
      "source_url": "https://example.com/fictional-deployment",
      "published_date": "2026-09-28",
      "summary": "A fictional company deployed an agent with per-action human approval.",
      "content": "Optional: the already-collected source text and supporting evidence.",
      "metadata": {"fictional": true}
    }
  ]
}
```

`id`, `title`, `source_url`, `published_date` and `summary` are required. Use the event's canonical stable slug as `id`; it is also the tie-break key for events recorded on the same date. Dates use `YYYY-MM-DD`; URLs must be HTTP(S).

`content`, `reddit_post_url` and `subreddit` are optional and may be omitted or null. Put any additional JSON data under the optional `metadata` object. Validation rejects unknown top-level or story fields, invalid types, blank required strings and duplicate IDs.

Supply one selected source per explicitly grouped event. You are responsible for event grouping, canonical source selection and assessment history. Do not pass revisions or repeated coverage as separate events. Different articles about the same event are not automatically recognised as duplicates, even with distinct IDs.

A source URL provides attribution; the application does not fetch it. Supply the original source evidence in `summary`, `content` and `metadata`. Do not base ratings on Reddit titles or comments. Without article content, the model works from the remaining supplied evidence and records its limitations.

This companion generates fresh assessments and reports. It does not ingest legacy assessment exports or enforce their database schema. Its `calculation.total_score` is the published weighted score. `calculation.raw_source_total` exposes the separate 0–13 sum for the editorial gate and integrations. See [Published score and severity](METHODOLOGY.md#6-published-score-and-severity) for the distinction.

## Evaluation stages

1. **Relevance chain.** Produces a relevance flag, score from 1 to 10, rationale and primary dimension. A story advances only when the flag is true and its score meets `minimum_relevance_score`.
2. **Criterion assessment.** Rates the three binary Trifecta checks and five amplifiers from 0 to 2, with a rationale for each, uncertainties and a separate leading-indicator flag. The model returns no totals, severity or clock calculations.
3. **Python calculation.** Derives the weighted score, severity and clock movement from those eight ratings.
4. **Editorial chain.** Writes a headline, metadata line, factual account and interpretation. Python attaches the stable story ID, severity and clock labels.

The relevance and writer stages are structured LLM chains without tools. The scorer is also a chain by default; optional hosted web search can check the supplied story. There is no agent framework or custom tool loop. All model outputs use strict JSON schemas and are validated with Pydantic.

The pipeline processes stories by recorded date, then canonical event ID. No publication-date cutoff or automatic rebasing applies.

The default relevance threshold is **2**, matching the filter the site actually runs. The site's unused configuration value of 5 is not used here. The rubric marks scores 1–2 as irrelevant, and contradictory positive flags trigger a correction attempt.

The default report threshold is **2 raw source points**, matching the saved writer branch. Every successfully assessed story contributes its published points even when below that reporting threshold or when report writing is disabled. Zero-score assessments remain in the output and do not move the clock.

## Deterministic scoring

Each Trifecta check is 0 or 1: ungoverned system access (T1), untrusted input exposure (T2), and permission and capability to act externally without per-action approval (T3).

| Active Trifecta checks | Points |
| ---: | ---: |
| 0 | 0 |
| 1 | 1 |
| 2 | 3 |
| 3 | 7 |

Add the five amplifier ratings: governance vacuum, autonomy without oversight, human capability erosion, emergent agency signals, and physical weaponisation. Each contributes 0, 1 or 2. The legacy `sentience_self_preservation` key remains for compatibility; behavioural agency signals do not establish consciousness. Controlled civilian embodiment can earn one physical point. The default maximum is **17**. T3 alone does not earn autonomy amplifier points; that amplifier needs separate evidence about the extent, duration or scale of operation beyond meaningful review.

| Score | Severity |
| --- | --- |
| 0 | NO MOVEMENT |
| 1–2 | CANARY |
| 3–4 | NOTABLE |
| 5–6 | SIGNIFICANT |
| 7–12 | CRITICAL |
| 13–17 | EXISTENTIAL |

With cumulative evidence points `B`, incident score `s`, initial seconds `T` and half-scale `H`:

```text
remaining_seconds(B) = T × 2^(-B / H)
incident_delta_seconds = remaining_seconds(B) - remaining_seconds(B + s)
gap_closed_percent = 100 × (1 - 2^(-s / H))
evidence_pressure_percent = 100 × (1 - 2^(-B / H))
```

Defaults are **`T = 900` seconds (15:00)** and **`H = 1000`**: every 1,000 points halve the remaining time. The initial display reference is borrowed once from IMD's September 2026 AI Safety Clock reading, as explained in methodology section 7; it does not add points or create a date cutoff.

Python calculates movement as `remaining_seconds(B) × gap_closed_percent / 100` using `expm1` to preserve tiny changes without subtracting nearly equal numbers. Evidence pressure measures the share of the initial symbolic window consumed, not the percentage of human control lost.

`clock.initial_evidence_points` starts a run from an existing cumulative total. Supplying that total does not provide history or prevent recounting earlier events. For corrections, rerun the complete caller-selected ledger from zero; a corrected score or grouping can move the recalculated clock in either direction. Scores never subtract evidence, grant recovery credit or decay over time.

Calculations retain unrounded values and reject evidence totals beyond `2**53 - 1` for compatibility with the official dataset engine. Floating-point underflow retains the smallest positive time and positive-event movement; a zero score remains exactly zero.

`format_remaining_time` rounds to the nearest second and displays values below one second as `<00:01`. `format_movement_seconds` distinguishes `NO MOVEMENT` from `<1 SECOND CLOSER`. `format_evidence_pressure` uses one decimal and displays values at or above 99.95 as `<100`.

The official 113-point example displays **13:52**. With 191 prior points, a full Trifecta plus autonomy = 2 scores **9 / CRITICAL**, closes **0.62%** of the remaining gap, moves **4.903 seconds**, and results in **13:03**. These examples are covered by offline regression tests.

The arithmetic is deterministic for the same validated ratings, configuration and event order. Model judgements and editorial text can vary between runs.

You can use the pure functions in [`scoring.py`](skynet_countdown/scoring.py), including `calculate_score`, `remaining_seconds`, `gap_closed_percent` and `evidence_pressure_percent`, independently of the API. For integrations, [`pipeline.py`](skynet_countdown/pipeline.py) exposes `evaluate(dataset, config, client=...)`. Criterion contracts live in [`models.py`](skynet_countdown/models.py), rubric instructions in [`prompts/`](skynet_countdown/prompts/), and published defaults in [`config.py`](skynet_countdown/config.py) and [`config.toml`](config.toml).

## Configuration

[`config.toml`](config.toml) contains all defaults and is read with Python's standard TOML parser. Unknown keys and invalid values fail validation.

| Settings | Meaning |
| --- | --- |
| `relevance`, `scorer`, `writer` | Per-stage `model`, `reasoning_effort`, `max_iterations`, `max_output_tokens` |
| `scorer.web_search` | Enable hosted search for this story; disabled by default |
| `scorer.web_search_context_size` | `low`, `medium` or `high` search context |
| `scorer.max_tool_calls` | Hosted tool-call limit per scorer request |
| `minimum_relevance_score`, `minimum_report_score`, `write_reports` | Relevance filtering and editorial generation; report threshold uses the raw source total |
| `request_timeout_seconds`, `api_max_retries` | SDK transport timeout and retries |
| `scoring.trifecta_points`, `scoring.severity_thresholds` | Weighted Trifecta table and inclusive severity boundaries |
| `clock.initial_seconds`, `clock.half_scale_points`, `clock.initial_evidence_points` | Clock calibration and starting evidence total |

`max_iterations` counts structured-output attempts, including the initial request. Further attempts correct schema or validation failures. A refusal or incomplete response fails that stage. Hosted search calls and SDK transport retries have their own settings and do not count towards `max_iterations`. `max_tool_calls` applies separately to each request, including a correction request.

Choose a model that supports the Responses API and structured outputs, plus web search if enabled. Reasoning values and tool support depend on the model. Set `reasoning_effort = "omit"` to leave out that API parameter.

You can change the scoring constants, but the result is a variant of the published default methodology. The derived maximum adjusts with the Trifecta table.

## Inspect the result

The JSON retains each input story alongside `relevance`, `assessment`, `calculation`, `report`, `status`, `error` and per-stage `runs`. Stages not reached are null. Run records include response IDs, returned model names, status, token usage, citations and web-search calls when available. The file also records the resolved configuration, prompt SHA-256 hashes, schema version, methodology version, calibration reference date, generation time, cumulative points, remaining seconds and evidence pressure.

`methodology_profile` is `published` when the scoring table, severity thresholds, starting window, sensitivity and relevance/report thresholds match the official defaults; otherwise it is `custom`. Model settings, disabling reports and supplying prior evidence do not change this profile. `calibration_effective_date` identifies the official reference calibration; the resolved configuration records any custom constants actually used.

Result schema **2.0** uses internal severity `NO_MOVEMENT`, displayed as “NO MOVEMENT”. It adds `raw_source_total`, evidence pressure and methodology metadata, and applies the raw editorial gate and canonical-ID ordering. Integrations consuming schema 1.0 should account for these differences.

Reports separate the factual story from interpretation. Metadata must be one lowercase line containing exactly three nonblank fragments separated by ` · `.

Excluded stories stay visible. If a stage fails, the pipeline records the failure against its story and continues with later stories. The file has `complete: false` and the CLI exits with a nonzero status. The pipeline does not invent replacement ratings. If writing fails after a successful calculation, that assessment and its points remain in the result. Review failed records before treating a run as complete.

## Contribute

Start with [`CONTRIBUTING.md`](CONTRIBUTING.md). The offline test suite uses the standard library and mocked API responses:

```sh
uv run python -m unittest discover -s tests -v
```

It makes no paid API calls. Changes to criteria, prompts or score calculations should include a concrete example and explain how they relate to the reference methodology. Licensed under [MIT](LICENSE).
