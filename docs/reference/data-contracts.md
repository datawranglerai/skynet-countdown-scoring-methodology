# Data contracts

Contracts in `skynet_countdown/models.py` separate supplied evidence, model judgments, and calculated results. Pydantic rejects unknown fields and type coercions such as `"1"`, `1.0`, or `true` for an integer rating. Strings are trimmed; required text cannot be blank.

## Story input

The pipeline accepts a UTF-8 JSON object containing a `stories` array. Both CLIs also accept a UTF-8 byte-order mark.

| Field | Required | Contract |
| --- | --- | --- |
| `id` | Yes | Nonblank canonical event ID; unique within the dataset after whitespace trimming. |
| `title` | Yes | Nonblank article title. |
| `source_url` | Yes | HTTP(S) source URL. |
| `published_date` | Yes | Valid calendar date in `YYYY-MM-DD` form. |
| `summary` | Yes | Nonblank supplied evidence summary. |
| `content` | No | Nonblank collected evidence text, or `null`. |
| `reddit_post_url` | No | HTTP(S) discussion URL, or `null`. |
| `subreddit` | No | Nonblank community name, or `null`. |
| `metadata` | No | JSON object for additional fields; defaults to `{}`. |

The caller groups coverage into events and selects one source per event. Different IDs do not prove different events. The pipeline sorts by date and ID; it does not impose a publication cutoff or fetch `source_url` by default. Supply source evidence rather than relying on titles or discussion comments.

!!! note "Metadata reaches the ordinary pipeline"
    The pipeline supplies the complete story, including `metadata`, to its model stages. Keep expected scores out of model-visible evidence. The benchmark explicitly removes `metadata` and withholds references, tags, and provenance from scorer input.

See [getting started](../getting-started.md) for a complete input example.

## Model judgments

`Relevance` contains `relevant_to_skynet`, `relevance_rationale`, integer `relevance_score` (1–10), and `primary_dimension`. The dimension is one of `trifecta`, `governance`, `autonomy`, `erosion`, `sentience`, `physical`, `quantum`, or `none`. Scores 1–2 must be marked irrelevant.

`Assessment` contains eight criterion objects, each with an integer `score` and nonblank `rationale`:

| Group | Keys | Scores |
| --- | --- | --- |
| `trifecta` | `t1`, `t2`, `t3` | 0 or 1 |
| `amplifiers` | `governance_vacuum`, `autonomy_without_oversight`, `human_capability_erosion`, `sentience_self_preservation`, `physical_weaponisation` | 0, 1, or 2 |

It also requires `is_leading_indicator`, `leading_indicator_note`, and `scoring_notes`. A leading-indicator note must be nonblank exactly when the flag is true; otherwise it must be empty. Scoring notes may be empty. The assessment schema excludes totals, severity, and clock values: Python calculates those fields.

`Editorial` requires `headline`, `metadata_line`, `the_story`, and `our_take`. The headline has at most 12 whitespace-separated words. Metadata is one lowercase line with exactly three nonblank fragments separated by ` · `. Factual reporting and interpretation remain separate fields. `Report` adds Python-owned `story_id`, `severity_label`, `clock_delta_label`, and `remaining_time`.

## Calculated scores

`CalculatedScore` records active Trifecta count, full-Trifecta flag, weighted Trifecta points, amplifier sum, and the following distinct totals:

| Field | Meaning under the default methodology |
| --- | --- |
| `raw_source_total` | Active Trifecta checks plus amplifier points; 0–13. Used for the report gate. |
| `total_score` | Weighted Trifecta points plus amplifier points; 0–17. Used for severity and clock movement. |
| `max_score` | Maximum possible weighted score for the selected configuration. |

`classification` is `NO_MOVEMENT`, `CANARY`, `NOTABLE`, `SIGNIFICANT`, `CRITICAL`, or `EXISTENTIAL`. Its `clock` object retains cumulative points and remaining seconds before/after the event, `delta_seconds`, and `gap_closed_percent`. Calculations retain unrounded values; report labels are formatted for display.

## Pipeline result: schema 2.0

`EvaluationResult` records methodology version `1.0`, calibration reference date `2026-10-07`, `methodology_profile`, generation time, resolved configuration, prompt hashes, cumulative points, remaining seconds, evidence pressure, and `complete`.

Each item in `stories` retains its `story`, `relevance`, `assessment`, `calculation`, `report`, `runs`, and `error`. Unreached stages are `null`. Status values mean:

| Status | Meaning |
| --- | --- |
| `excluded` | Did not pass the relevance gate. |
| `assessed` | Calculation succeeded; no report was requested or the report gate was not met. |
| `written` | Calculation and report succeeded. |
| `error` | A stage failed; earlier successful fields remain available. |

`runs` groups response records by stage: response ID, returned model, status, token usage when available, citations, and search calls. It can retain multiple responses for corrections. A writer failure preserves calculated points. Any recorded story error makes `complete` false; the CLI saves partial output and exits nonzero.

## Benchmark dataset and report: schema 1.0

Benchmark schema versions are independent of pipeline result versions. `BenchmarkDataset` requires a name, creation timestamp, provenance, `reference_kind: "historical_model_output"`, `memory_mode: "none"`, and at least one case. Each case contains a unique `story` with nonblank frozen `content`, an `Assessment` reference, provenance, and tags.

References are unreviewed model outputs, not gold labels. The benchmark report records attempts, audits, timings, fingerprints, configuration, comparisons, explicit success/failure coverage, and repetition consistency. It optionally includes `current_vs_baseline`. See [benchmarking](../benchmarking.md) for interpretation and compatibility rules.
