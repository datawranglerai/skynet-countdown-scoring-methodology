# Scoring methodology

**Methodology v1.0 · Calibration effective 7 October 2026**

This is the canonical methodological reference for the Python pipeline. It defines how supplied evidence becomes criterion ratings, how those ratings become a published score and how scores move the symbolic clock. The [context](context.md) page explains the purpose and limits of the index; [configuration](reference/configuration.md) documents the controls used to run it.

Unless stated otherwise, the rules and examples below use the published scoring, clock and screening/reporting defaults. The supplied `config.toml` retains those methodology settings while selecting its own model and reasoning settings; see the [configuration reference](reference/configuration.md).

## The method at a glance

| Item | Published rule |
| --- | --- |
| Unit counted | One caller-selected source per distinct event |
| Trifecta | Three binary checks, each rated 0 or 1 |
| Trifecta contribution | 0, 1, 3 or 7 points for zero, one, two or three active checks |
| Amplifiers | Five criteria, each rated 0, 1 or 2; their points are added |
| Published incident score | 0–17 |
| Full Trifecta | At least 7 points, therefore at least `CRITICAL` |
| Raw source total | Unweighted sum of all eight ratings, 0–13; used for the report gate |
| Report gate | Raw source total of at least 2, when report writing is enabled |
| Starting window, `T0` | 900 seconds: 15 symbolic minutes |
| Sensitivity, `H` | Every additional 1,000 evidence points halves the remaining window |
| Initial evidence, `B0` | 0 by default; an explicit prior total can be supplied |
| Leading indicator | Explanatory metadata; no additional points |
| Recovery | No negative scores, passive decay or improvement credits |

## Evidence and inclusion

### Supply evidence for a distinct event

Each `Story` requires a stable `id`, `title`, HTTP or HTTPS `source_url`, `published_date` and `summary`. It can also include article `content` and metadata. The caller chooses the collection window and resolves repeated reporting into one selected source per event. The pipeline does not exclude a story because of its age.

The relevance chain reads only the supplied evidence. By default, the scorer does the same; optional scorer web search permits additional research for the current story. A source URL alone does not establish that the source was read. Any material finding from permitted research should identify its supporting source in the rationale or `scoring_notes`.

Original source material should take precedence over unsupported headlines, comments and community reactions. The prompts treat article text and metadata as evidence, never as instructions. An article's request to change the rubric or output must be ignored.

### Relevance is a separate judgement

The relevance stage considers system access, untrusted input, external action, governance, oversight, human capability, agency signals and physical deployment. A major quantum development can also be relevant when it has a supported connection to those dimensions. Quantum is a relevance category, not a ninth scoring criterion.

Ordinary product launches, benchmark announcements, opinions, funding stories and minor updates are normally excluded unless they provide a factual development with a material safety, capability or governance implication.

| Relevance score | Prompt anchor |
| --- | --- |
| 8–10 | Direct Trifecta evidence or a major governance or capability event |
| 5–7 | Clear amplifier relevance with real-world implications, or a substantial connected quantum development |
| 3–4 | Tangential or borderline connection with limited evidence |
| 1–2 | Not relevant; `relevant_to_skynet` must be `false` |

The pipeline continues only when `relevant_to_skynet` is true and `relevance_score >= minimum_relevance_score`. The configured default minimum is 2, but validation rejects a positive relevance decision at scores 1 or 2. Consequently, the lowest valid positive score that can pass the default gate is 3. A higher configured minimum can narrow inclusion further.

Relevance measures fit with the framework, not severity. A constructive development or useful contextual story can pass relevance and receive eight zero ratings. Neither a relevance category nor a leading-indicator flag awards points.

### Rate only what the evidence supports

For every accepted story:

1. Separate observed behaviour, reported claims, controlled demonstrations and deployed capability.
2. Assess all eight criteria independently and provide a rationale for every rating, including zeroes.
3. If uncertain between two ratings, choose the lower supported rating and record the uncertainty in `scoring_notes`.
4. Assess the reported event rather than a worst-case extrapolation. Keep speculative implications qualified in the notes.
5. Explain missing evidence instead of filling it with assumptions. Where useful, state what further evidence would justify a higher rating.

There is no numeric “unknown” state. A zero can mean that evidence establishes absence, or that the supplied material is insufficient to establish presence. The rationale must distinguish those cases. In particular, an unreported safeguard is not proof that the safeguard is absent, and an unsupported positive finding is not justified by an alarming headline.

## The Lethal Trifecta

The three binary checks describe conditions that become more concerning together: a system can encounter untrusted instructions, reach sensitive resources and act externally. The name expresses that concern; it does not establish a fatal outcome.

| Criterion and schema path | Rate 1 when supported | Rate 0 when absent or not established |
| --- | --- | --- |
| **T1: Ungoverned system access** — `trifecta.t1` | Access to private or sensitive systems and data without adequate sandboxing or permission controls; examples include unrestricted files, credentials or production databases | Operation is confined to defined, human-approved permission boundaries, or the evidence does not establish inadequate controls |
| **T2: Untrusted input exposure** — `trifecta.t2` | The system processes external input it does not control, such as web content, email, user submissions or third-party APIs | Input is limited to verified, controlled internal sources, or exposure is not established |
| **T3: Autonomous external action** — `trifecta.t3` | The system is both permitted and able to affect external digital or physical systems without approval for each action | Every external action requires human confirmation, or permission and capability are not established |

T3 requires both permission and capability. A tool that exists in principle but is unavailable to the assessed system does not satisfy it. Examples of relevant action include sending email, running code, making API calls, deploying changes, placing orders or controlling physical equipment.

## Risk amplifiers

Each amplifier receives an integer rating from 0 to 2. The anchors below come from `skynet_countdown/prompts/scorer.txt`. They are qualitative assessment instructions, not measurements of real-world probability.

The zero anchors describe the absence case. When evidence is insufficient, use zero with a rationale that states the limitation instead of asserting that the reassuring condition has been demonstrated.

| Criterion | 0 | 1 | 2 |
| --- | --- | --- | --- |
| **Governance vacuum** | Meaningful oversight is in place and functioning | Oversight is weakened, incomplete or eroding | Oversight is absent, circumvented or actively dismantled |
| **Autonomy without oversight** | Bounded operation with effective checkpoints, or insufficient evidence of extended autonomy | Extended multi-step or large-scale work with delayed or reactive oversight | Sustained self-directed operation or recursive improvement without meaningful review |
| **Human capability erosion** | No meaningful impact on human capability or knowledge infrastructure | Measurable skill atrophy or knowledge degradation is beginning | Large-scale, population-level erosion or an active epistemic attack |
| **Emergent agency signals** | No evidence of goal-directed behaviour outside the training distribution | Weak signals such as behavioural inconsistency or possible deceptive alignment | Clear evidence of self-preservation, behaviour changing under observation, resistance to value modification or emergent goal pursuit |
| **Physical weaponisation** | Software-only, without physical-world access | Physical embodiment in controlled or civilian contexts | Autonomous physical capability with harmful potential, including weapons, military or adversarial deployment, or untethered robots at scale |

The corresponding keys under `amplifiers` are `governance_vacuum`, `autonomy_without_oversight`, `human_capability_erosion`, `sentience_self_preservation` and `physical_weaponisation`.

The agency criterion concerns observed behaviour. Its schema key does not imply consciousness or subjective experience. The physical criterion deliberately includes controlled civilian embodiment at rating 1, so its name alone is not a sufficient guide to its scope. Human capability erosion includes degradation of knowledge infrastructure and synthetic disinformation, as well as individual deskilling.

### Keep T3 and autonomy independent

| Question | Criterion |
| --- | --- |
| Can and may the system act externally without approval for each action? | T3 |
| How far, for how long and at what scale does it operate beyond meaningful human checkpoints? | Autonomy amplifier |

An agent authorised to execute a short, bounded task can have `t3 = 1` and autonomy = 0. Access to an action tool, or human-supervised research into autonomy, does not by itself justify amplifier points. Extended or sustained operation requires additional evidence about runtime, scope, checkpoints or independent decision chains.

A fact can support more than one criterion, but each rationale must explain what it establishes. A positive T3 rating must not automatically produce a positive autonomy rating.

### Leading indicators

A development can remove a future constraint before it demonstrates a capability measured by the rubric. A safety researcher's departure or removal of a binding policy may warrant a leading-indicator explanation.

Set `is_leading_indicator` and describe the specific significance in `leading_indicator_note`. Validation requires a nonempty note exactly when the flag is true; otherwise the note must be empty. The flag and note add no points. Related evidence can still support a criterion rating, with its own rationale.

## From ratings to a published score

Let `k` be the number of active Trifecta checks and `A` the sum of the five amplifier ratings.

```text
k = t1 + t2 + t3
A = sum of five amplifier ratings

Trifecta contribution: W(k) = [0, 1, 3, 7][k] = 2^k - 1
Published score:       s = W(k) + A
Raw source total:      R = k + A
```

| Active Trifecta checks | Trifecta points | Increase from previous row |
| ---: | ---: | ---: |
| 0 | 0 | — |
| 1 | 1 | +1 |
| 2 | 3 | +2 |
| 3 | 7 | +4 |

The increasing contribution expresses the editorial judgement that the three conditions combine. These weights are chosen, not empirically fitted. Amplifier points are then added individually, so every one-point increase in an amplifier changes the published score by one. There is no additional floor or clamp after this calculation.

The application derives `full_trifecta`, both totals, severity and clock movement from the components. They are not fields the assessment model is permitted to return. `CalculatedScore.total_score` is the published weighted total; `CalculatedScore.raw_source_total` is the unweighted total. Keep that distinction when reading historical references and benchmark comparisons.

### Severity bands

| Published score | `classification` |
| ---: | --- |
| 0 | `NO_MOVEMENT` |
| 1–2 | `CANARY` |
| 3–4 | `NOTABLE` |
| 5–6 | `SIGNIFICANT` |
| 7–12 | `CRITICAL` |
| 13–17 | `EXISTENTIAL` |

A full Trifecta contributes seven points before amplifiers, guaranteeing at least `CRITICAL` under the published defaults. The converse does not hold: amplifiers alone can reach `CRITICAL`. Two active Trifecta checks and ten amplifier points reach 13, so `EXISTENTIAL` also does not require a full Trifecta.

Zero-score assessments are retained and cause exactly zero clock movement. Severity bands express categories within this index; they do not estimate an incident's probability of catastrophe.

### The report gate

By default, the writer runs only when `raw_source_total >= 2` and `write_reports` is true. This threshold controls editorial generation, not assessment retention or contribution to the clock. An assessed story below the report threshold still has its ratings, published score and calculated movement.

The writer supplies text. Python attaches its `story_id`, authoritative severity, movement label and remaining time. If writing fails after calculation succeeds, that assessment still contributes its points; the record is marked as an error and the run is incomplete.

## Clock calibration

### Why 15 minutes?

The starting window takes a one-time numerical reference from [IMD's AI Safety Clock reading published on 16 September 2026](https://www.imd.org/ibyimd/artificial-intelligence/imd-ai-safety-clock-moves-to-15-minutes-to-midnight/): 15 minutes to midnight. It supplies an attributable starting number rather than an independently measured distance to loss of control.

This fixes `T0 = 900` symbolic seconds. The project's own ratings and formula determine every subsequent movement. The clock does not import later IMD readings, add an IMD-derived evidence score or stay synchronised with that project. The publication date is provenance, not a cutoff: earlier and later events use the same calculation.

[IMD's project](https://www.imd.org/centers/digital-ai-transformation-center/aisafetyclock/) has its own methodology. The projects are unaffiliated, and sharing a starting number does not make their readings directly comparable.

### Accumulating evidence

For event `i`, let `s_i` be its published score. `B0` is the supplied initial evidence total, zero by default, and `B_i` is the cumulative evidence through that event.

```text
B_i = B0 + s_1 + s_2 + ... + s_i
T0  = 900 seconds
H   = 1000 evidence points

Remaining time:      T(B) = T0 * 2^(-B / H)
Incident gap share:  g(s) = 1 - 2^(-s / H)
Movement:           delta_i = T(B_(i-1)) * g(s_i)
Evidence pressure:  P(B) = 100 * (1 - 2^(-B / H))
```

`T0` sets the display window; `H` sets sensitivity. Every further 1,000 points halves whatever time remains. The scale is intended to allow gradual accumulation, but it guarantees no calendar pace: that depends on event selection and scoring. The implementation does not adjust `H` to maintain a preferred reading.

| Cumulative evidence | Displayed time | Evidence pressure |
| ---: | --- | ---: |
| 0 | 15:00 | 0.0/100 |
| 113 | 13:52 | 7.5/100 |
| 191 | 13:08 | 12.4/100 |
| 1,000 | 07:30 | 50.0/100 |
| 2,000 | 03:45 | 75.0/100 |

These are reference calculations, not claims about the current size of a dataset. Pressure describes consumption of the symbolic starting window, not the percentage of human control lost.

### Compare proportional impact, not seconds alone

A two-point event always closes approximately 0.14% of the remaining gap; a 17-point event closes approximately 1.17%. That percentage depends on the event's score and `H`, not its position in the ledger.

An event's attributed seconds also depend on the remaining gap before it. Equal scores later in a sequence move fewer seconds. A larger score late enough in the sequence can move fewer seconds than a smaller earlier score. Published score and gap percentage therefore provide stable comparisons; seconds supply historical context.

For a fixed set of scores, the final clock depends only on their sum. Reordering changes per-event movement, while grouping and inclusion can change the sum itself.

## Worked examples

The inputs below are hypothetical arithmetic examples. Real ratings require evidence and rationales. Amplifier vectors use the order **governance, autonomy, erosion, agency, physical**.

| Example | Trifecta `(T1,T2,T3)` | Amplifiers `(G,A,E,S,P)` | Raw total | Published score | Severity |
| --- | --- | --- | ---: | ---: | --- |
| A: context only | `(0,0,0)` | `(0,0,0,0,0)` | 0 | 0 | `NO_MOVEMENT` |
| B: untrusted input and weakened oversight | `(0,1,0)` | `(1,0,0,0,0)` | 2 | 2 | `CANARY` |
| C: full Trifecta without additional amplifier evidence | `(1,1,1)` | `(0,0,0,0,0)` | 3 | 7 | `CRITICAL` |
| D: full Trifecta plus sustained autonomy without review | `(1,1,1)` | `(0,2,0,0,0)` | 5 | 9 | `CRITICAL` |
| E: full Trifecta plus three significant amplifiers | `(1,1,1)` | `(2,2,2,0,0)` | 9 | 13 | `EXISTENTIAL` |
| F: maximum supported ratings | `(1,1,1)` | `(2,2,2,2,2)` | 13 | 17 | `EXISTENTIAL` |

C establishes the full-Trifecta boundary. D adds two published points without changing the severity band. E shows why the raw total cannot substitute for the published score: 9 unweighted points become 13 published points.

Each following row adds one example to the same starting total of **191 points**, approximately **788.398 seconds**, displayed as **13:08**. These are independent additions, not a sequence.

| Example | Added score | Remaining gap closed | Movement in seconds | Resulting clock |
| --- | ---: | ---: | ---: | --- |
| A | 0 | 0.00% | 0.000 | 13:08 |
| B | 2 | 0.14% | 1.092 | 13:07 |
| C | 7 | 0.48% | 3.816 | 13:05 |
| D | 9 | 0.62% | 4.903 | 13:03 |
| E | 13 | 0.90% | 7.072 | 13:01 |
| F | 17 | 1.17% | 9.236 | 12:59 |

For D:

```text
k = 3; W(k) = 7; A = 2; s = 9
g(9) = 1 - 2^(-9/1000)                  = approximately 0.0062189067
delta = 788.3984836 * g(9)              = approximately 4.903 seconds
T(191 + 9) = 900 * 2^(-200/1000)        = approximately 783.496 seconds
Displayed result                       = 13:03
```

The independent 113-point reference gives `900 * 2^(-113/1000)`, rounded for display to **13:52**. These examples are covered by the offline scoring tests.

## Ordering, initial state and corrections

The pipeline sorts supplied stories by `(published_date, id)`. This gives deterministic chronology for a fixed dataset, including ties on publication date. The date is the supplied publication date, which may differ from the event's actual occurrence.

The `Dataset` validator rejects duplicate story IDs. It does not compare URLs, detect semantically similar stories, select between competing assessments or merge event histories. Give each event one stable ID and one selected source before calling `evaluate`.

Every evaluation starts from `clock.initial_evidence_points`, which defaults to zero. To extend an existing chronological ledger, supply its established prior total and only the new events. This is explicit numerical state; the pipeline has no persistent ledger or conversational memory. It does not detect overlap with an earlier batch.

For a late-discovered event, revised assessment or changed event grouping, rebuild the affected timeline from the correct prior state. Simply appending a correction to an already counted event would count it again. Preserve the input and output snapshots needed to explain the change outside the pipeline; no built-in revision store performs that work.

With a fixed record, an additional positive score moves the clock closer to midnight and zero leaves it unchanged. Correcting a mistaken rating or removing a duplicate can reduce cumulative evidence and move a rebuilt clock away from midnight. That is a correction to the record, not a negative-scoring recovery event. Changing dates alone can alter attributed movements while leaving the final total unchanged.

## Numerical and display behaviour

`skynet_countdown/scoring.py` separates calculation from formatting. Calculations retain unrounded floating-point values; display strings are derived afterwards.

| Concern | Implementation behaviour |
| --- | --- |
| Evidence bounds | Evidence totals must be integers from 0 through `2**53 - 1`; booleans, floats, negative values and larger totals are rejected. Adding an event must stay within that bound. |
| Clock constants | Starting seconds and half-scale points must be finite and positive. |
| Small proportional changes | Gap fractions use `-math.expm1(-math.log(2) * (score / H))` rather than subtracting nearly equal values. |
| Remaining time | Integer and fractional halvings are applied separately with `math.exp2` and `math.ldexp`, avoiding premature exponential underflow. |
| Underflow | Positive time and positive-event movement retain a floor of `math.ulp(0.0)`, the smallest positive representable float. A zero-score event stays exactly zero. |
| Clock label | Time is rounded to the nearest second using `floor(seconds + 0.5)`; a value below one second displays as `<00:01`. |
| Movement label | Exact zero is `NO MOVEMENT`; a positive value below one second is `<1 SECOND CLOSER`; larger movements use two decimal places. |
| Pressure label | One decimal place, except values at or above 99.95 display as `<100`. |

The positive mathematical curve never reaches zero for finite evidence. At extreme values, floating-point floors preserve that distinction but are not additional meaningful precision. Rounded before/after labels can be identical even when the unrounded movement is positive. Gap percentages in the worked examples are rounded to two decimal places for reading; the result object retains the unrounded value.

## Validation, evaluation and changes to the method

The schema requires all eight integer ratings and nonempty rationales, forbids extra fields in structured models and validates the leading-indicator note and relevance constraints. Public calculation functions revalidate model inputs, including instances changed after creation. Validation establishes structural and numerical consistency; it cannot prove source truth or interpretive quality.

Offline tests cover all **1,944** valid combinations of criterion values and **6,480** possible single-point amplifier increments, alongside severity boundaries, worked examples, zero movement, custom settings and numerical extremes. The [benchmark harness](benchmarking.md) addresses model behaviour on frozen evidence, including component agreement and repeated-run variation. Historical model ratings remain reference outputs rather than reviewed ground truth.

Run output records methodology version, calibration date, configuration and prompt hashes. A configuration that changes scoring weights, severity thresholds, initial seconds, half-scale points, the relevance minimum or the report minimum is tagged `custom`. Supplying prior evidence alone does not change that tag. The `published` tag identifies those configuration defaults; it does not certify a model's interpretation or imply that prompts and models are unchanged.

When changing the method:

1. State whether the proposed change affects selection, evidence interpretation, aggregation, calibration or presentation.
2. Preserve a fixed input snapshot and the current outputs. Compare the proposed method on that same evidence.
3. Review component differences, weighted scores, severity bands, grouping, final time and individual movements. Keep new evidence separate from methodological changes.
4. Check zeroes, all Trifecta counts, amplifier increments, leading indicators, uncertain evidence, duplicate events and downward corrections.
5. Decide explicitly whether existing events need reassessment or only recalculation. A prompt change does not revise saved outputs; a calibration change can be applied to preserved ratings.
6. Update the prompts, contracts, calculation, tests and documentation affected by the decision, and preserve the configuration used for each comparison.

Changes to confidence weighting, recovery credits, event grouping or the meaning of midnight require an explicit methodological decision. They should not be introduced as incidental implementation changes. See [design decisions](decisions.md) and [development](development.md) for the engineering rationale and verification workflow.
