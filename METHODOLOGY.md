# The Skynet Countdown: methodology

**Methodology v1.0 · Calibration effective 7 October 2026**

This is the scoring reference for the open-source Python companion to
[Skynet Countdown](https://skynetcountdown.org). It explains how supplied evidence becomes an
assessment, how Python calculates its score and how scores move the symbolic clock. It also records
the assumptions and implementation limits so maintainers can evaluate or improve the method.

The formulas, score bands and worked examples below use the published defaults. The
[README](README.md) covers input, configuration and output. The live site's collection, storage and
presentation systems are outside this repository.

## Contents

1. [Purpose and scope](#1-purpose-and-scope)
2. [The method at a glance](#2-the-method-at-a-glance)
3. [Evidence and assessment](#3-evidence-and-assessment)
4. [The Lethal Trifecta](#4-the-lethal-trifecta)
5. [Risk amplifiers](#5-risk-amplifiers)
6. [Published score and severity](#6-published-score-and-severity)
7. [Why the clock starts at 15 minutes](#7-why-the-clock-starts-at-15-minutes)
8. [Clock calculation](#8-clock-calculation)
9. [Worked examples](#9-worked-examples)
10. [Limitations](#10-limitations)
11. [Improving the method](#11-improving-the-method)

## 1. Purpose and scope

The Skynet Countdown is an editorial index of evidence that AI systems are moving beyond meaningful
human control. Midnight represents a world in which AI is sufficiently capable, autonomous and
ungoverned that meaningful human oversight becomes structurally impossible.

The clock metaphor draws on
the [Bulletin of the Atomic Scientists' Doomsday Clock](https://thebulletin.org/doomsday-clock/).
The 15-minute numerical starting reference comes from IMD, as explained
in [section 7](#7-why-the-clock-starts-at-15-minutes).

The index organises selected evidence. It does not estimate a probability of catastrophe, an
extinction date, time available to respond, or the actual percentage of human control remaining. A
classification such as EXISTENTIAL is a band in this scoring system; it does not establish that an
individual incident causes an existential catastrophe.

The method combines three kinds of decision:

- **Editorial choices.** Which developments to include, what constitutes one event, which assessment
  to select, the criterion definitions, score weights and clock constants.
- **Assessment judgements.** Whether the evidence supports each criterion and, for amplifiers, how
  strongly it supports it.
- **Deterministic calculations.** The published score, severity, proportional impact and clock
  position once those choices and ratings are fixed.

### The Python companion

The companion evaluates stories you have already collected and writes one local JSON result. You
choose the time window, group coverage into events and supply one selected source per event. You
also retain assessment history. The application rejects duplicate story IDs, but does not recognise
repeated coverage with different IDs or reconcile event groups.

The relevance, scorer and writer stages use AI to produce judgements and editorial text. Python
validates their outputs and calculates scores. Validation establishes structural and numerical
consistency. It does not establish that a source is true or that the model interpreted it correctly.
You decide what human review to perform before supplying evidence or accepting results; the
companion has no mandatory human fact-checking gate.

For corrections, update the caller-selected dataset and rerun it from zero cumulative points. A
corrected rating or event grouping can move the recalculated clock in either direction. Archive the
input, configuration and result if you need to compare revisions; the companion does not keep a
history store.

## 2. The method at a glance

| Item                   | Published default                                                                                 |
|------------------------|---------------------------------------------------------------------------------------------------|
| Unit counted           | One selected assessment per explicitly grouped event                                              |
| Trifecta               | Three binary criteria, each rated 0 or 1                                                          |
| Trifecta contribution  | 0, 1, 3 or 7 points for zero, one, two or three active criteria                                   |
| Amplifiers             | Five criteria, each rated 0, 1 or 2; all points are added                                         |
| Published score        | 0–17                                                                                              |
| Full Trifecta          | At least 7 points, therefore at least CRITICAL                                                    |
| Starting window, `T₀`  | 900 seconds: 15 symbolic minutes                                                                  |
| Sensitivity, `H`       | 1,000 cumulative evidence points halve the remaining window                                       |
| Clock                  | `T(B) = 900 × 2^(−B / 1000)`                                                                      |
| Stable incident impact | `100 × (1 − 2^(−s / 1000))` per cent of the remaining gap                                         |
| Leading-indicator flag | Explanatory metadata; awards no extra points                                                      |
| Recovery               | No negative scores, passive decay or credit for improvements                                      |
| Corrections            | Caller corrects the selected dataset and reruns it; the clock can change in either direction      |

The pipeline orders supplied stories by `published_date`, then canonical event `id`. The same
calculation applies regardless of a story's age. There is no cutoff at the IMD publication date and
no automatic rebasing as the dataset grows.

### Published and custom configurations

[`config.toml`](config.toml) can change the Trifecta weights, severity thresholds, clock constants and
relevance/report thresholds. Custom weights can change the maximum score; custom clock constants
can change the calculated times. Treat those runs as variants of the published methodology.

The result's `methodology_profile` is `published` when the scoring table, severity thresholds,
starting window, sensitivity and relevance/report thresholds match the published defaults.
Otherwise it is `custom`. Model settings, disabling reports and supplying prior evidence do not
change this profile. Each result records the resolved configuration, methodology version and prompt
hashes. See [Configuration](README.md#configuration) for all settings.

## 3. Evidence and assessment

### Inclusion

A development should supply factual evidence relevant to at least one criterion or a meaningful
leading indicator. Relevant topics include system access, untrusted inputs, autonomous action,
governance failures, loss of human checking capacity, agency signals and consequential physical
deployment.

The [relevance prompt](skynet_countdown/prompts/relevance.txt) normally excludes ordinary product
launches without safety or governance implications, benchmarks without real-world consequences,
opinion without new factual developments, funding news without a relevant capability or governance
angle, and minor incremental updates. A topic label or dramatic headline earns no points by itself.

Supply original source evidence in `summary`, optional `content` and `metadata`. The `source_url`
provides attribution; the default pipeline does not fetch it. Reddit titles and comments can help
you find sources, but should not replace the original evidence in an assessment.

The relevance and writer stages use only supplied data. Scorer web search is disabled by default.
Set `scorer.web_search = true` to allow hosted search to check the supplied story. The scorer must
identify retrieved evidence supporting a material finding in its rationale or `scoring_notes`.

### Relevance and reporting gates

A story reaches the scorer only when `relevant_to_skynet` is true and `relevance_score` meets
`minimum_relevance_score`, which defaults to 2. The rubric marks relevance scores 1–2 as irrelevant,
and validation rejects a positive relevance flag for those scores. Failed validation can trigger a
correction attempt.

Every successfully calculated assessment adds its published points to the cumulative total. A
report is generated only when `write_reports` is enabled and `calculation.raw_source_total` meets
`minimum_report_score`, which defaults to 2. Stories below the reporting threshold still contribute
their points, and disabling reports does not disable scoring. Zero-score assessments remain visible
and contribute no movement.

### Assessment procedure

1. Before running the companion, identify the event, source URL, `published_date` and stable canonical
   `id`. Check for repeated coverage and supply one selected source per event.
2. The relevance and scorer stages read the supplied evidence. Separate observed behaviour from
   forecasts, speculation and promotional claims; a URL alone does not supply article content.
3. Rate all eight criteria. Give a specific rationale for each rating, including zeroes.
4. Score the incident described, rather than a feared extrapolation. The scorer prompt instructs the
   model to choose the lower supported score when uncertain and record that uncertainty in
   `scoring_notes`.
5. Assess T3 and the autonomy amplifier separately. The capability to act does not establish
   extended operation without oversight.
6. Flag a leading indicator when useful, and explain it in `leading_indicator_note`. The flag does
   not change the score.
7. Where a report is generated, keep the factual story and editorial interpretation separate. The
   result retains the supplied story, source link, assessment, calculation and report together.
   Archive runs yourself when tracking revisions.

Missing component values are invalid input. A numeric zero records a completed judgement: absent
evidence or insufficient evidence to justify a positive rating. The format has no separate numeric
“unknown” state, so the rationale must explain which meaning applies. This distinction matters when
comparing assessment quality.

## 4. The Lethal Trifecta

Each criterion is binary: 1 when supported by the incident evidence, otherwise 0 with a rationale.
The keys below are fields under each story's `assessment.trifecta` object in the result JSON.

| Key  | Criterion                  | Evidence being assessed                                                                                                   |
|------|----------------------------|---------------------------------------------------------------------------------------------------------------------------|
| `t1` | Ungoverned system access   | Access to private systems, credentials or sensitive data without adequate permission boundaries                           |
| `t2` | Untrusted input exposure   | Exposure to open-web, email, user or third-party input the system does not control                                        |
| `t3` | Autonomous external action | Permission and capability to affect external digital or physical systems without mandatory human approval for each action |

The checks describe conditions that can combine: a system can encounter an untrusted instruction,
reach sensitive resources and act on it. Their name expresses the concern about that combination; it
is not proof that an incident is fatal or that all three conditions cause a particular outcome.

T3 includes both permission and capability. A hypothetical tool capability that is unavailable to
the deployed system does not establish the condition. Conversely, a system may have T3 while
operating within a short, bounded task with meaningful checkpoints. Extended autonomy needs
additional evidence under the amplifier below.

## 5. Risk amplifiers

All five amplifiers contribute independently to the arithmetic, with ratings from 0 to 2. A shared
piece of evidence may be relevant to several criteria, but the rationale must explain what it
establishes for each one; one positive rating must not automatically trigger another.

The table records the current scorer prompt's anchors. These are qualitative assessment
instructions, not numerical measurements of real-world risk. The keys are fields under each story's
`assessment.amplifiers` object; each contains a `score` and `rationale`.

| JSON key and published label                                  | 0                                                                                           | 1                                                                              | 2                                                                                                                                           |
|---------------------------------------------------------------|---------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------|
| `governance_vacuum` — Governance vacuum                         | Meaningful oversight in place and functioning                                               | Oversight weakened, incomplete or showing signs of erosion                     | Oversight absent, circumvented or actively being dismantled                                                                                 |
| `autonomy_without_oversight` — Autonomy without oversight        | Bounded operation with effective checkpoints, or insufficient evidence of extended autonomy | Extended multi-step or large-scale work with delayed or reactive oversight     | Sustained self-directed operation or recursive improvement without meaningful review                                                        |
| `human_capability_erosion` — Human capability erosion            | No meaningful impact on human capability or knowledge infrastructure                        | Measurable skill atrophy or knowledge degradation beginning                    | Large-scale, population-level erosion or an active epistemic attack                                                                         |
| `sentience_self_preservation` — Emergent agency signals          | No evidence of goal-directed behaviour outside the training distribution                    | Weak signals such as behavioural inconsistency or possible deceptive alignment | Clear evidence of self-preservation, behaviour changing under observation, resistance to value modification or emergent goal pursuit        |
| `physical_weaponisation` — Physical weaponisation               | Software-only, without physical-world access                                                | Physical embodiment in controlled or civilian contexts                         | Autonomous physical capability with harmful potential, including weapons, military or adversarial deployment, or untethered robots at scale |

The legacy `sentience_self_preservation` key remains for compatibility. The criterion describes
behavioural agency signals; those signals do not establish consciousness or subjective experience.

The physical criterion's label is narrower than its prompt anchors: a controlled civilian embodiment
can score 1. Human capability erosion also includes knowledge degradation and epistemic attacks in
the prompt. Keep these details visible when refining the labels or rubric.

### T3 and the autonomy amplifier

| Question                                                                           | Criterion          |
|------------------------------------------------------------------------------------|--------------------|
| Can and may the system act externally without approval for each action?            | T3                 |
| How far, how long and at what scale does it operate beyond meaningful checkpoints? | Autonomy amplifier |

For example, an agent permitted to execute an approved short task can have T3 = 1 and autonomy = 0.
Evidence that it conducts sustained self-directed work without meaningful review can justify
autonomy = 2. The additional rating needs its own evidence and rationale.

## 6. Published score and severity

Let `k = t1 + t2 + t3` and let `A` be the sum of the five amplifier ratings.

```text
Trifecta contribution W(k) = [0, 1, 3, 7][k] = 2^k − 1
Published incident score s = W(k) + A
```

The result keeps two totals separate:

- **Raw source total.** `calculation.raw_source_total` is the unweighted sum `k + A`, ranging from
  0 to 13. It controls the report threshold and is available to integrations.
- **Published score.** `calculation.total_score` is `W(k) + A`, ranging from 0 to 17 under the
  published weights. It determines severity and clock movement.

| Active Trifecta checks | Trifecta points | Contribution of the next check |
|-----------------------:|----------------:|-------------------------------:|
|                      0 |               0 |                             +1 |
|                      1 |               1 |                             +2 |
|                      2 |               3 |                             +4 |
|                      3 |               7 |                              — |

The increasing contribution reflects the editorial judgement that the conditions become more
concerning together. The weights are chosen, not empirically fitted.

Every amplifier point then adds one published point. This guarantees a complete Trifecta is at least
CRITICAL while preserving the effect of every amplifier. There is no separate post-calculation floor
or clamp that would give several different inputs the same effective score.

| Published score | Displayed classification |
|----------------:|--------------------------|
|               0 | NO MOVEMENT              |
|             1–2 | CANARY                   |
|             3–4 | NOTABLE                  |
|             5–6 | SIGNIFICANT              |
|            7–12 | CRITICAL                 |
|           13–17 | EXISTENTIAL              |

Severity is derived solely from the published total. A full Trifecta guarantees at least CRITICAL,
but CRITICAL does not imply a full Trifecta. A sufficiently large amplifier total can also reach
that band. Two active Trifecta checks plus all ten amplifier points reach 13, so EXISTENTIAL also
does not require all three checks.

Zero-score events remain in the result and contribute exactly zero movement. `NO_MOVEMENT` is the
severity value in the JSON result; the tables display it with a space.

## 7. Why the clock starts at 15 minutes

The clock starts at 15 symbolic minutes to midnight, the
reading [IMD's AI Safety Clock](https://www.imd.org/ibyimd/artificial-intelligence/imd-ai-safety-clock-moves-to-15-minutes-to-midnight/)
published in September 2026. We could have picked any number. Sixty minutes would have been a tidy
invention with nothing behind it; IMD's figure is dated, attributable and checkable by anyone who
wants to look. Their reading is itself an editorial judgement, but a published one from an
independent body, which is more purchase than a number chosen in the dark.

From the first incident onward, everything is ours. The scores, the formula, the movement of the
hands, all of it comes from our own assessments and our own arithmetic. We set our watch from IMD's
once. It doesn't stay synchronised.

In the default configuration, `T₀ = 900` seconds. The date identifies the published reference we
borrowed; it does not create a cutoff in our ledger. Incidents before September 2026 are included in
the same calculation as later incidents. We do not add an IMD-derived evidence score to our total or
periodically import new IMD readings.

The [IMD project](https://www.imd.org/centers/digital-ai-transformation-center/aisafetyclock/) has
its own methodology. The projects are unaffiliated, and sharing a starting number does not make
their readings directly comparable. Our use of that reference supplies attribution and context, not
an empirical estimate of the distance to loss of control.

## 8. Clock calculation

### Constants and cumulative evidence

For the selected events ordered by `published_date` then `id`, using the published defaults and no
prior evidence, let:

- `sᵢ` be event `i`'s published score;
- `Bᵢ = Σ sⱼ` for events through `i`;
- `B₀ = 0` before the first event;
- `T₀ = 900` symbolic seconds;
- `H = 1000` evidence points.

```text
Remaining time:       T(B) = T₀ × 2^(−B / H)
Incident gap share:   g(s) = 1 − 2^(−s / H)
Movement in seconds:  ΔTᵢ = T(Bᵢ₋₁) × g(sᵢ)
Evidence pressure:   P(B) = 100 × (1 − 2^(−B / H))
```

To continue from an existing cumulative total, set `clock.initial_evidence_points`. This replaces
the zero starting total above. Supply only events not already represented by that seed: a prior
total does not restore event history or prevent recounting. For corrections, rerun the complete
caller-selected dataset from zero.

Mathematically, `ΔTᵢ = T(Bᵢ₋₁) − T(Bᵢ)`. The implementation calculates movement using the
proportional expression to preserve very small positive movements without subtracting nearly equal
numbers.

### What the constants do

`T₀` sets the display window. `H` sets sensitivity: every further 1,000 points halves whatever time
remains. Keeping `H` fixed means scores have the same proportional effect throughout the history.

We chose the 1,000-point scale for gradual accumulation over months of ordinary coverage. It does
not guarantee a calendar pace; the pace depends on which events are included and how they are
scored. It is not automatically adjusted to keep the clock near a preferred reading.

| Cumulative points | Symbolic time remaining | Evidence pressure |
|------------------:|-------------------------|------------------:|
|                 0 | 15:00                   |           0.0/100 |
|               113 | 13:52                   |           7.5/100 |
|               191 | 13:08                   |          12.4/100 |
|             1,000 | 07:30                   |          50.0/100 |
|             2,000 | 03:45                   |          75.0/100 |

These are reference calculations covered by the [offline scoring tests](tests/test_scoring.py).

### Comparing incidents

Use the score and percentage of the remaining gap closed to compare incident impact. A two-point
event always closes about 0.14% of the remaining gap; a 17-point event always closes about 1.17%.

An event's movement in seconds depends on its position in the ledger. An equally scored event later
in the history moves fewer seconds because the remaining interval is smaller. At sufficiently
different starting positions, a larger score can move fewer seconds than a smaller earlier score.
This is a property of the curve. Seconds give historical context; use scores and gap percentages for
stable severity comparisons.

For fixed selected scores, the final time depends only on their sum, not their order. Reordering
changes each event's attributed seconds. Grouping matters because it determines which events and
assessments contribute to that sum.

The result's `evidence_pressure_percent` represents `P(B)`: the share of the initial symbolic window
consumed. It is not an estimate of the percentage of human control lost. The live website's dial and
history chart are presentation choices outside this repository.

## 9. Worked examples

### Component ratings to published scores

These hypothetical inputs illustrate the arithmetic. A real assessment still needs evidence and
rationale for every rating. Amplifier vectors are ordered **governance, autonomy, erosion, agency,
physical**.

| Example                                            | Trifecta `(T1,T2,T3)` | Amplifiers `(G,A,E,S,P)` | Raw source total | Published score | Classification |
|----------------------------------------------------|-----------------------|--------------------------|-----------------:|----------------:|----------------|
| A: context only                                    | `(0,0,0)`             | `(0,0,0,0,0)`            |                0 |               0 | NO MOVEMENT    |
| B: untrusted input and weakened oversight          | `(0,1,0)`             | `(1,0,0,0,0)`            |                2 |               2 | CANARY         |
| C: full Trifecta, no additional amplifier evidence | `(1,1,1)`             | `(0,0,0,0,0)`            |                3 |               7 | CRITICAL       |
| D: C plus sustained autonomy without review        | `(1,1,1)`             | `(0,2,0,0,0)`            |                5 |               9 | CRITICAL       |
| E: full Trifecta plus three significant amplifiers | `(1,1,1)`             | `(2,2,2,0,0)`            |                9 |              13 | EXISTENTIAL    |
| F: maximum supported ratings                       | `(1,1,1)`             | `(2,2,2,2,2)`            |               13 |              17 | EXISTENTIAL    |

For B, imagine a system handling untrusted external input while oversight has weakened, with no
supported evidence of sensitive-system access or permission for autonomous external action. Its one
Trifecta check contributes 1; governance adds 1; total = 2.

C is the full-Trifecta boundary case. D adds evidence of sustained operation beyond meaningful
review: its autonomy rating adds two points immediately, even though the classification stays
CRITICAL. This is why the Trifecta contribution is calculated before adding amplifiers.

E demonstrates why the raw source total must not supply published severity. Its raw total is
9, while the weighted published score is 13.

### Scores to movement

Each row below is an independent hypothetical addition to the same starting evidence base of **191
points**, where the unrounded remaining time is approximately **788.398 seconds**, displayed as
**13:08**. The rows are not a sequence.

| Example | Added score | Remaining gap closed | Movement, seconds | Resulting clock |
|---------|------------:|---------------------:|------------------:|-----------------|
| A       |           0 |                   0% |             0.000 | 13:08           |
| B       |           2 |                0.14% |             1.092 | 13:07           |
| C       |           7 |                0.48% |             3.816 | 13:05           |
| D       |           9 |                0.62% |             4.903 | 13:03           |
| E       |          13 |                0.90% |             7.072 | 13:01           |
| F       |          17 |                1.17% |             9.236 | 12:59           |

For D:

```text
k = 3
W(k) = 7
A = 2
s = 9
g(9) = 1 − 2^(−9/1000) ≈ 0.0062189067
ΔT = 788.3984836 × g(9) ≈ 4.903 seconds
T(191 + 9) = 900 × 2^(−200/1000) ≈ 783.496 seconds → 13:03
```

The same nine-point score at the initial 15:00 baseline would close the same percentage of the gap
but a larger number of seconds.

## 10. Limitations

- **Coverage bias.** More reporting, more sources or a different collection cadence can add points
  without a corresponding change in the world. There is no denominator for total AI activity or
  successful safe deployments.
- **Deduplication limits.** The companion rejects duplicate IDs but does not identify repeated
  coverage under different IDs or group events for you. Caller-selected event boundaries can affect
  totals substantially.
- **Assessment uncertainty.** Qualitative terms such as significant, sustained and meaningful
  require judgement. Zero can reflect either absence or insufficient evidence. There are no numeric
  confidence weights or confidence intervals.
- **Correlated criteria.** Governance, access and autonomy may describe related aspects of one
  failure. Separate rationales help expose this, but the additive model has no learned correction
  for correlation beyond the chosen Trifecta weighting.
- **Different contexts.** A controlled evaluation, observed deployment and hypothetical warning can
  concern similar capabilities while having different evidential strength and consequences. The
  present score has no separate experiment-versus-deployment multiplier; the distinction belongs in
  the source account and rationale.
- **Leading indicators.** Early institutional changes can matter while scoring modestly. Their flag
  preserves context but gives no additional movement.
- **No recovery model.** Improvements receive no negative points. Corrections can revise the ledger,
  but they are not a formal measure of restored control.
- **Automation.** A structurally valid AI assessment can still contain an unsupported claim,
  fabricated connection or poor interpretation. Human fact-checking and inter-rater agreement are
  not guaranteed by the software.
- **Symbolic calibration.** The IMD reference, Trifecta weights, severity bands and 1,000-point
  sensitivity are editorial choices. Reproducibility makes them inspectable; it does not establish
  predictive validity.
- **No terminal test.** The asymptote cannot determine that loss of control has occurred, and the
  present method has no separate empirical rule that declares midnight.

## 11. Improving the method

### Questions worth testing

1. **Rubric reliability.** Can independent assessors reach similar ratings from the same evidence?
   Assemble a benchmark of source excerpts, ratings, rationales and disagreements, including absent
   and uncertain cases. Refine the criteria where agreement is poor.
2. **Evidence strength.** Should controlled demonstrations, verified deployments, allegations and
   forecasts have distinct recorded fields or inclusion rules? Define those distinctions before
   introducing confidence multipliers.
3. **Event boundaries.** What counts as a new development versus repeated reporting or a revision?
   Test grouping on multi-source incidents and sustained programmes of work.
4. **Criterion overlap.** Examine whether access, governance and autonomy repeatedly count the same
   underlying fact. Compare alternatives while preserving explicit rationales for each component.
5. **Severity interpretation.** Test whether readers understand the bands and whether the thresholds
   separate meaningful differences. A higher band is an ordinal editorial category, not a measured
   increase in catastrophic probability.
6. **Recovery.** Define observable evidence of restored safeguards, the duration of that restoration
   and how reversals would work before adding a negative contribution. Keep this separate from
   correction of a mistaken assessment.
7. **Sensitivity.** Compare candidate values of `H` on a fixed event set and explicit coverage-rate
   scenarios. Assess how quickly ordinary and high-scoring events consume the gap. Repeatedly
   fitting `H` to a desired current time would weaken longitudinal comparability.
8. **Collection bias.** Measure which sources, regions, sectors and incident types are missing.
   Evaluate the caller's time window, source selection and relevance settings before treating
   observed event volume as a trend in underlying risk. The report threshold changes report
   coverage, not assessed points.

### How to change the method

1. State the problem, proposed rule and expected effect in plain language. Identify whether it
   changes evidence selection, judgement, aggregation, calibration or presentation.
2. Archive the supplied dataset, resolved configuration and result used for comparison. Keep
   proposed ratings separate from the baseline until reviewed.
3. Run both methods over that same snapshot. Report changed component ratings, scores, bands, event
   groups, final time and per-event impacts; explain whether changes come from the method or new
   evidence.
4. Check boundary cases: all zeroes, every Trifecta count, full Trifecta with each amplifier
   increment, maximum scores, leading indicators, uncertain evidence, duplicate reports and downward
   corrections.
5. Specify how history should be treated and which future records the rule applies to. Record the
   decision in the method/version metadata and documentation before changing published behaviour.
   The published v1.0 defaults use one rule across all selected history.
6. Update the relevant code, prompts, validators and schema together. The CLI evaluates supplied
   stories afresh; it does not load archived assessments. For a rubric change, rerun the selected
   dataset and retain the new result for comparison. For a pure calibration change, integrations can
   use [`scoring.py`](skynet_countdown/scoring.py) to recompute time from existing scores.
7. Keep this document, README, configuration, prompts and tests consistent. Preserve source
   attribution and distinguish the borrowed IMD starting reading from our own calculation. Changes
   to the public website and its documentation require separate coordination.

Changes to weights, recovery or confidence need explicit methodological decisions and evidence.
Handle those separately from documentation edits. See [CONTRIBUTING.md](CONTRIBUTING.md) for this
repository's contribution and verification process.
