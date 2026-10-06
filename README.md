# Skynet Countdown: scoring methodology

An open-source Python companion to [Skynet Countdown](https://skynetcountdown.org). Bring your own collected stories, inspect the model's evidence judgements, and reproduce the published scoring calculation locally.

This project starts after collection and scraping. It does not discover stories, scrape Reddit or articles, reconcile duplicate events, manage assessment history, allocate CVE identifiers, or publish to SQL, Sheets or Slack. It writes one local JSON result. The index is editorial: its clock is symbolic, not a forecast or a probability of catastrophe.

The [site methodology](references/SKYNET_COUNTDOWN_SITE_README.md) is the scoring authority. The [original n8n workflow](n8n/Skynet%20Countdown%20v1.2.json) provides the relevance, criterion-assessment and editorial stages; its calculated totals and clock values are not used.

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

Evaluation sends supplied story fields to OpenAI and incurs API charges. The default model is `gpt-5.4` with high reasoning effort; adjust `config.toml` to suit your needs and model access. Existing environment variables work too: the application itself does not load `.env`.

The output path must be new and its parent directory must exist. Existing files are never overwritten. Use `--config path/to/config.toml` to select another configuration. This is a small uv project run directly from its checkout, with the OpenAI SDK and Pydantic as its only runtime dependencies.

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

`id`, `title`, `source_url`, `published_date` and `summary` are required. Dates use `YYYY-MM-DD`; URLs must be HTTP(S). `content`, `reddit_post_url` and `subreddit` are optional and may be omitted or null. Put any additional JSON data under the optional `metadata` object. Unknown top-level or story fields are rejected, as are invalid types, blank required strings and duplicate IDs.

Supply stable IDs and each event only once. Different articles about the same event are not automatically recognised as duplicates, even with distinct IDs. A source URL is attribution, not fetched content: provide enough evidence in `summary`, `content` and `metadata` for the assessment. Without article content, the model works from the remaining supplied evidence and records its limitations.

## Evaluation stages

1. **Relevance chain:** produces a relevance flag, score from 1 to 10, rationale and primary dimension. A story advances only when the flag is true and its score meets `minimum_relevance_score`.
2. **Criterion assessment:** rates the three binary Trifecta checks and five amplifiers from 0 to 2, with a rationale for each, uncertainties and a separate leading-indicator flag. The model returns no totals, severity or clock calculations.
3. **Python calculation:** derives the weighted score, severity and clock movement from those eight ratings.
4. **Editorial chain:** writes a headline, metadata line, factual account and interpretation. Python attaches the stable story ID, severity and clock labels.

The relevance and writer stages are structured LLM chains without tools. The scorer is also a chain by default; optional hosted web search can check the supplied story. There is no agent framework or custom tool loop. All model outputs use strict JSON schemas and are validated with Pydantic.

Stories are processed oldest first; equal dates retain input order. The default relevance threshold is **2**, matching the n8n filter actually executed; its unused configuration value of 5 is not adopted. The default report threshold is **2 weighted points**. Every successfully assessed story contributes its points even when below that reporting threshold or when report writing is disabled. Zero-score assessments remain in the output and do not move the clock.

## Deterministic scoring

Each Trifecta check is 0 or 1: ungoverned system access (T1), untrusted input exposure (T2), and permission and capability to act externally without per-action approval (T3).

| Active Trifecta checks | Points |
| ---: | ---: |
| 0 | 0 |
| 1 | 1 |
| 2 | 3 |
| 3 | 7 |

Add the five amplifier ratings: governance vacuum, autonomy without oversight, human capability erosion, sentience/self-preservation, and physical embodiment/weaponisation. Each contributes 0, 1 or 2. The default maximum is **17**. T3 alone does not earn autonomy amplifier points; that amplifier needs separate evidence about the extent, duration or scale of operation beyond meaningful review.

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
```

Defaults are `T = 3600` and `H = 1000`: every 1,000 points halve the remaining time. `clock.initial_evidence_points` starts a run from an existing cumulative total. Supplying that total does not provide history or prevent recounting earlier events. Scores never subtract evidence. The reference's separate “evidence pressure” display has no supplied formula and is not implemented.

The arithmetic is deterministic for the same validated ratings, configuration and event order. Model judgements and editorial text can vary between runs. The pure functions in [`scoring.py`](skynet_countdown/scoring.py) can be used independently of the API; [`pipeline.py`](skynet_countdown/pipeline.py) exposes `evaluate(dataset, config, client=...)` for integrations.

## Configuration

[`config.toml`](config.toml) contains all defaults and is read with Python's standard TOML parser. Unknown keys and invalid values fail validation.

| Settings | Meaning |
| --- | --- |
| `relevance`, `scorer`, `writer` | Per-stage `model`, `reasoning_effort`, `max_iterations`, `max_output_tokens` |
| `scorer.web_search` | Enable hosted search for this story; disabled by default |
| `scorer.web_search_context_size` | `low`, `medium` or `high` search context |
| `scorer.max_tool_calls` | Hosted tool-call limit per scorer request |
| `minimum_relevance_score`, `minimum_report_score`, `write_reports` | Filtering and report generation |
| `request_timeout_seconds`, `api_max_retries` | SDK transport timeout and retries |
| `scoring.trifecta_points`, `scoring.severity_thresholds` | Weighted Trifecta table and inclusive severity boundaries |
| `clock.initial_seconds`, `clock.half_scale_points`, `clock.initial_evidence_points` | Clock calibration and starting evidence total |

`max_iterations` counts structured-output attempts, including the initial request. Further attempts correct schema or validation failures; refusals and incomplete responses fail that stage. It does not count hosted search calls or SDK transport retries, which have their own settings. `max_tool_calls` applies separately to each request, including a correction request.

Choose a model that supports the Responses API and structured outputs, plus web search if enabled. Reasoning values and tool support depend on the model. Set `reasoning_effort = "omit"` to leave out that API parameter. Changing scoring constants is supported, but produces a variant of the published default methodology; the derived maximum adjusts with the Trifecta table.

## Inspect the result

The JSON retains each input story alongside `relevance`, `assessment`, `calculation`, `report`, `status`, `error` and per-stage `runs`. Stages not reached are null. Run records include response IDs, returned model names, status, token usage, citations and web-search calls when available. The file also records the resolved configuration, prompt SHA-256 hashes, schema version, generation time, cumulative points and remaining seconds.

Excluded stories stay visible. A stage failure is recorded against its story, later stories still run, and the file has `complete: false`; the CLI exits with a nonzero status. No replacement ratings are invented. If writing fails after a successful calculation, that assessment and its points remain in the result. Review failed records before treating a run as complete.

## Contribute

Start with [`CONTRIBUTING.md`](CONTRIBUTING.md). The offline test suite uses the standard library and mocked API responses:

```sh
uv run python -m unittest discover -s tests -v
```

It makes no paid API calls. Changes to criteria, prompts or score calculations should include a concrete example and explain how they relate to the reference methodology. Licensed under [MIT](LICENSE).
