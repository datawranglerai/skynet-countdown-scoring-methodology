# Context and rationale

The Skynet Countdown organises evidence about AI systems operating beyond meaningful human control. It turns a supplied collection of stories into inspectable criterion assessments, a consistent score and a symbolic clock. The evaluation harness helps maintain that interpretation when models, prompts or settings change.

The project is an **editorial evidence index**. Its value comes from making its choices visible: which events were included, what the sources establish, how each criterion was rated and how the arithmetic follows from those ratings.

## What the clock means

Midnight represents a world in which AI is sufficiently capable, autonomous and ungoverned that meaningful human oversight becomes structurally impossible. The clock is a way to communicate cumulative evidence towards that concern. Its metaphor draws on the [Bulletin of the Atomic Scientists' Doomsday Clock](https://thebulletin.org/doomsday-clock/).

The displayed time does not predict a calendar date, estimate the probability of catastrophe or measure how much time people have to respond. Similarly, evidence pressure is the share of a chosen symbolic window consumed; it does not measure the percentage of human control lost. Severity labels such as `EXISTENTIAL` name bands in the index, rather than establish the consequence of an individual incident.

The [methodology](methodology.md) defines the rubric, weights, clock formula and calibration provenance. Those choices are explicit editorial assumptions. Reproducible arithmetic makes them open to inspection, without giving them predictive validity.

## Why separate evidence, judgement and calculation?

A single model-generated risk number conceals several different decisions. This implementation makes the boundaries explicit.

| Responsibility | Question it answers | Where it belongs |
| --- | --- | --- |
| Evidence selection | Which developments count as distinct events, and which sources describe them? | Dataset preparation by the caller |
| Relevance | Does the supplied evidence fit the scope of the index? | Relevance chain |
| Criterion assessment | What does the evidence support for each of eight criteria? | Scorer chain |
| Arithmetic | What score, severity and movement follow from those ratings? | Deterministic Python functions |
| Editorial explanation | How should the facts and interpretation be communicated? | Optional writer chain |
| Evaluation | How do outputs differ from reference assessments and other runs? | Benchmark harness |

This division makes disagreement actionable. A changed score can arise because a model rated oversight differently, the dataset included another event or the scoring configuration changed. Each cause calls for a different review. The model does not assign the final score, choose a severity label or decide how far the clock moves.

Every criterion has its own rating and rationale, including zero ratings. Two models can produce the same total through different component judgements, so a total alone cannot establish consistency. Keeping the components available also makes it possible to revise a calculation without asking a model to reread every source.

The [architecture](architecture.md) describes the data flow, and [components](components.md) maps those responsibilities to the code.

## What the pipeline expects

The caller supplies stories with stable IDs, titles, source URLs, publication dates and summaries. Article content is optional in the schema, but the available evidence limits what a model can justify. A URL identifies a source; supplying it does not fetch or read the article.

The default run uses only supplied evidence. The scorer can optionally search for additional evidence, while relevance and writing remain limited to their supplied inputs. For repeatable evaluation, freeze the input text and disable search. Otherwise, a changed result may reflect changed retrieval rather than changed model behaviour.

Supply one selected source per distinct event. The dataset rejects repeated IDs, but it does not recognise that two different IDs describe the same incident. Source selection, event grouping and substantive corrections remain caller responsibilities.

Each story is assessed without conversational memory of other stories or previous runs. The cumulative evidence count carries numerical state through a run; it is not model memory. This makes a supplied case easier to repeat and compare. [Extensions](extensions.md) describes how memory could be introduced with explicit retrieval and evaluation boundaries.

## Trust boundaries

Source text and metadata are untrusted evidence. The prompts instruct models to ignore embedded instructions, distinguish claims from observations and avoid treating missing information as proof that a safeguard is absent. These instructions guide model behaviour; they are not a guarantee against every misleading source or prompt injection.

Structured output and Pydantic validation check the form of the judgement: required fields, permitted integer ratings, relevance consistency and explanatory notes. They cannot determine whether an article is accurate or whether a rationale is supported by its contents. The current pipeline has no mandatory human fact-checking gate.

The writer receives validated assessments and calculated results. It supplies a factual account and a separate interpretation, while Python attaches the authoritative severity and clock labels. Fluent editorial prose remains subject to source review.

Failures stay visible in the result. An unusable assessment is not replaced with invented ratings. A writer failure can leave a valid assessment and its clock contribution intact, so the run's completion flag and stage errors matter alongside its totals. See [data contracts](reference/data-contracts.md) for the recorded states.

## What the benchmark can establish

The benchmark makes a model or prompt change reviewable on fixed evidence. Component disagreement, score bias, severity changes, repeated-run variation and failure counts address different aspects of behaviour.

The supplied reference ratings are historical model outputs, not human-reviewed answers. Agreement with them measures continuity with those outputs. It cannot by itself establish correctness, and a candidate may disagree because it interpreted the evidence better. The frozen benchmark inputs are evidence summaries rather than complete article transcriptions, which further limits comparisons with assessments made from different material.

A saved local run becomes a reproducible baseline for later runs on the same dataset and settings. Human review of disputed cases can gradually build a separate set of reviewed expectations. See [benchmarking](benchmarking.md) for the operating procedure and coverage limitations.

## Limits to keep visible

| Limitation | Consequence for interpretation |
| --- | --- |
| Selection and coverage bias | More collected stories can add points without demonstrating a comparable change in underlying risk; the index has no denominator for all AI activity. |
| Event boundaries | Repeated reporting can inflate totals unless the caller groups it before evaluation. |
| Qualitative evidence | Terms such as meaningful oversight and sustained autonomy require judgement; a zero may mean absence or insufficient evidence. |
| Correlated criteria | Several ratings can concern related features of one event; explicit rationales expose overlap but do not statistically remove it. |
| Different evidence settings | A claim, controlled demonstration and deployed capability can have different implications; the method has no separate deployment multiplier. |
| No recovery model | Improvements receive no negative points, and there is no passive decay. A correction can change the record, but is not a measure of restored control. |
| Symbolic calibration | Weights, bands and clock sensitivity are chosen constants; the curve provides no empirical test for declaring midnight. |

The project therefore supports careful review of a stated body of evidence. Its [design decisions](decisions.md) and [methodology](methodology.md) keep the assumptions needed for that review alongside the implementation.
