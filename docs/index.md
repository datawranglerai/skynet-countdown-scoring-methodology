---
title: Overview
description: Understand the Skynet Countdown methodology, run its Python scoring pipeline, and compare model behaviour on frozen evidence.
hide:
  - toc
---

<div class="docs-intro" markdown>

<p class="docs-eyebrow">Skynet Countdown · Methodology & engineering</p>

# Evidence-led scoring. Inspectable decisions.

Turn supplied AI news into structured evidence judgements, a reproducible score, and an optional editorial report. Check whether those judgements stay consistent when the model changes.

[Run your first assessment](getting-started.md){ .md-button .md-button--primary }
[Understand the method](methodology.md){ .md-button }

</div>

Skynet Countdown is an **editorial index of developments affecting meaningful human control over AI**. Its clock is a symbolic display of accumulated evidence. It does not estimate a catastrophe probability or predict when an event will occur.

The implementation uses explicit Python chains with the OpenAI Responses SDK. Models screen stories, rate evidence and write prose. Python computes the score, severity and clock movement. The evaluation harness reuses the same scorer with frozen evidence and independent requests.

<div class="grid cards docs-paths" markdown>

-   **Understand the context**

    Why this index exists, what it measures, and where judgement and uncertainty enter the process.

    [Context and rationale →](context.md)

-   **Follow the calculation**

    Three binary checks, five amplifiers, a 17-point maximum and an explicit clock equation.

    [Scoring methodology →](methodology.md)

-   **Inspect the system**

    Trace a story through screening, assessment, deterministic calculation and optional reporting.

    [Architecture and components →](architecture.md)

-   **Evaluate a model change**

    Compare component ratings on 40 frozen cases, measure repeat consistency and retain failures.

    [Benchmark harness →](benchmarking.md)

</div>

## A small, explicit system

| Boundary | What happens there |
| --- | --- |
| Input | You supply selected, already-collected evidence for each distinct event. |
| Model judgement | Structured chains return relevance, eight ratings with rationales, and optional editorial prose. |
| Deterministic calculation | Python derives weighted points, severity, cumulative evidence and the clock display. |
| Evaluation | Independent scorer runs are compared with historical references and a compatible saved model baseline. |

Start with an offline input check; it needs no credentials:

```sh
uv run python -m skynet_countdown --input examples/stories.json --validate-only
```

Then follow the [quick start](getting-started.md) for a live assessment. For integration, use the [Python API](reference/python-api.md); for changes to the implementation, read the [design decisions](decisions.md).

!!! note "Two different kinds of confidence"
    The arithmetic is deterministic for validated ratings and configuration. The ratings themselves are model judgements. Historical benchmark agreement measures continuity, and repeated runs measure consistency; neither establishes correctness without reviewed evidence and reference labels.

## Where to go next

| Your question | Read |
| --- | --- |
| What evidence earns a point? | [Methodology](methodology.md) |
| Which setting controls a stage? | [Configuration](reference/configuration.md) |
| What does each JSON field mean? | [Data contracts](reference/data-contracts.md) |
| Why was the system built this way? | [Design decisions](decisions.md) |
| How could memory or hosted evaluation fit? | [Extensions and memory](extensions.md) |
| How do I test or build the documentation? | [Development](development.md) |
| Why did an assessment or comparison fail? | [Troubleshooting](troubleshooting.md) |
