# Scorer benchmarks

The benchmark measures agreement with historical model ratings and consistency across fresh runs. Its references are **unreviewed historical model outputs**, as confirmed by the export owner. They are not a correctness standard. A disagreement can reveal a better interpretation of the rubric, incomplete evidence, a changed source, or an error in either assessment.

## The initial dataset

`examples/benchmarks/benchmark.json` contains 40 distinct events selected from PostgreSQL exports. The source files are `examples/benchmarks/assessments.json` and `examples/benchmarks/stories.json`. The latter contains generated editorials, not original articles. These files live in the repository and are not published as site assets.

All 75 supplied assessment URLs were attempted on 12 October 2026. The retrieval pass returned HTML for 57, failed for 17, and encountered one PDF. The 40 selected pages were checked for substantive event-specific content. One otherwise successful extraction was rejected because the Amazon page yielded an older shareholder letter. Retrieval success alone did not qualify a page for inclusion. `examples/benchmarks/source_manifest.json` records every attempt, redirects, hashes and selection outcomes.

The frozen model inputs contain **concise paraphrased evidence summaries from the retrieved pages**, not full article transcriptions. Each case records the extraction method, retrieval time, original and resolved URLs, response and extracted-text hashes, and a hash of its frozen evidence. The full-page review cache is local working material, not a required or distributed dataset component. Summarisation is another source of uncertainty: review the original source and packet before adjudicating a disagreement. Some retrieved pages have changed since their historical assessment; these are not reconstructed historical snapshots.

Cases retain attribution, reported controls, simulation boundaries, uncertainty and distinctions between allegations and observed events. Scoring references, old rationales, editorials, provenance and selection tags are kept outside the model input. All source review and paraphrasing was performed by coding assistants; neither the evidence packets nor ratings have received human adjudication.

Selection uses event IDs, source identity and reported-event overlap. Repeated `cve_id` values in the exports are unsuitable as unique identifiers. The selected cases include 23 distinct historical rating vectors. With the published weighting their reference classifications are:

| Classification | Cases |
| --- | ---: |
| NO MOVEMENT | 8 |
| CANARY | 12 |
| NOTABLE | 10 |
| SIGNIFICANT | 3 |
| CRITICAL | 7 |

This is a deliberately varied starting sample, not a random sample of production news. It has no EXISTENTIAL references, no amplifier ratings of 2 for human capability erosion or emergent agency signals, and no labelled irrelevant cases. It cannot measure relevance precision/recall, writer quality or live retrieval quality. Stories about prompt injection are not tests of whether this scorer resists injected instructions.

Verified source publication dates are available for 27 cases. The remaining 13 use the exported incident date, explicitly marked in provenance. Historical raw totals and classifications remain as provenance only. The runner recomputes both reference and candidate totals and classifications from their eight ratings using the same configured Python arithmetic. It never compares the old suggested clock movements.

## Run locally

Validate the fixtures without credentials, retrieval or model calls:

```sh
uv run python -m skynet_countdown.benchmark --dataset examples/benchmarks/benchmark.json --validate-only
```

To establish the first memory-free model baseline, provide the API credentials used by the normal pipeline:

```sh
uv run --env-file .env python -m skynet_countdown.benchmark --dataset examples/benchmarks/benchmark.json --config config.toml --repetitions 3 --output benchmark-baseline.json
```

This runs 120 scorer assessments, plus any structured-output corrections and transport retries. It incurs model API charges. Use one repetition for a cheaper first check; repeat-consistency measurements need at least two. The output must be a new file in an existing directory.

Compare another model against that saved run:

```sh
uv run --env-file .env python -m skynet_countdown.benchmark --dataset examples/benchmarks/benchmark.json --config config.toml --model YOUR_CANDIDATE_MODEL --repetitions 3 --baseline benchmark-baseline.json --output benchmark-candidate.json
```

Use an actual model identifier available to your account. The configured reasoning settings must be supported by both models. Supply a different TOML file with `--config` when needed. The strict saved-run comparison accepts a model change and a different repetition count, but requires matching evidence, scorer instructions, scoring contracts and other active settings. A prompt, rubric or reasoning-setting experiment needs a separate baseline rather than being presented as an isolated model comparison.

Each case and repetition is a new scorer request. Relevance filtering and report writing are skipped; web search is disabled; the clock baseline is zero. Story metadata is excluded from scorer payloads as an additional separation from archived labels. Existing structured-output validation and correction attempts still run. The ordinary pipeline and its defaults are unchanged.

Results are local JSON. This command neither uploads experiments to LangSmith nor schedules future work. Keep generated reports out of source control unless intentionally publishing a reviewed result.

## Interpret a report

- **Historical agreement:** component matches and signed deltas, weighted-score differences, severity/full-Trifecta changes, and leading-indicator differences. A positive score delta means the new assessment assigned more points. These are differences from model-generated references, not an accuracy claim.
- **Current versus saved baseline:** per-case mean ratings and mean weighted scores across successful repetitions, with paired-case counts and coverage for both runs. This is the appropriate comparison for subsequent memory-free model changes.
- **Repeat consistency:** variation in component ratings or the leading-indicator flag across repetitions. Cases with failed or missing repetitions are reported separately; they are not counted as stable.
- **Reliability and cost evidence:** failed assessments, structured-output correction attempts, returned model identifiers, response IDs, recorded token usage and elapsed time. SDK transport retries are not counted as structured-output corrections. Token totals cover responses whose usage was returned; they are not billing estimates.

Agreement statistics are explicitly conditional on successful assessments. Always inspect completion and coverage alongside them. The report preserves failures; no replacement scores are invented. The CLI exits nonzero for incomplete runs and input/configuration errors. Historical disagreement by itself does not fail the command, and the harness does not automatically approve a model swap.

Pin the evidence and config for comparisons. Run before changing the scoring model and periodically on the incumbent. Review changed cases, especially full-Trifecta flips and evidence for autonomy beyond T3. Establish normal repeat variation before choosing numerical acceptance thresholds. A small sample and a few repetitions do not establish statistical significance. Record model snapshots where available, retain the returned model name, and keep an accepted report as the next operational baseline.

The historical execution context, original retrieval results, and model/prompt settings are unavailable. Differences from the exports therefore cannot be attributed solely to model drift. Establish the first local baseline before using subsequent comparisons for that purpose. The [architecture](architecture.md) shows how the harness isolates the scorer from the other stages.

## Improve the references

Review the frozen evidence and rubric with a person before labelling a case as correct. Particularly review historical autonomy ratings assigned to ordinary chatbot responses, supervised research or bounded demonstrations, and inconsistent treatment of simulated actions. Per-case review flags identify known examples; they are not automatic corrections.

Keep human-approved reference revisions separate from historical labels, with reviewer, rationale, rubric version and source evidence. Add irrelevant and boundary cases as separate labelled fixtures when extending evaluation to relevance. Preserve a small set of unseen cases when tuning prompts. Existing pure comparison functions can later be adapted to LangSmith code evaluators while keeping the dataset and scoring rules in the repository; no hosted service is needed for this first harness.

## Optional memory later

Keep the default pipeline stateless. If memory is introduced, make it an explicit, optional input at the orchestration boundary, with retrieval/storage owned by the caller. The existing `Story.metadata` can carry a small context snapshot for an experimental integration, but avoid putting archived target ratings there; the current benchmark intentionally drops metadata.

Start with bounded, versioned context such as methodology decisions or caller-selected prior events. Record the exact context sent to the model, its source IDs, ordering, cutoff date and hash. Do not include the current case's reference answer or information recorded after the event cutoff. A database connection or conversational history should not become necessary to run the existing scorer.

For a memory-enabled benchmark, add an explicit context field and pass frozen context into the scorer only through a dedicated opt-in mode. Replay a fixed starting snapshot independently for each repetition. If evaluating updates to memory across an event sequence, define the sequence and restore the same initial state before each run. Keep separate baselines for memory-enabled and memory-free conditions, and compare their evidence quality and consistency before adopting the extension. See [extensions and memory](extensions.md) for the integration boundaries and reproducibility requirements.
