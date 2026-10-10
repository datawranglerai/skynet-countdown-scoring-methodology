# Contributing

Contributions should make the methodology easier to inspect, reproduce or apply to supplied stories. Keep changes small and explain the behaviour they improve. Please discuss new dependencies or broader collection, storage and publishing features before adding them.

## Development

Use Python 3.13+ and run from the repository root:

```sh
uv sync
uv run python -m skynet_countdown --input examples/stories.json --validate-only
uv run python -m unittest discover -s tests -v
```

Validation and tests do not require credentials or make paid API calls. Keep automated tests offline using mocked responses. If you separately test a real model, report the model and relevant settings; do not commit credentials or private source material.

## Where to work

- `skynet_countdown/models.py`: input, structured model outputs and result contracts.
- `skynet_countdown/prompts/`: relevance, criterion assessment and editorial instructions.
- `skynet_countdown/scoring.py`: deterministic scoring and clock arithmetic.
- `skynet_countdown/llm.py`: structured API requests, correction attempts and run provenance.
- `skynet_countdown/pipeline.py`: stage ordering, filtering and failure handling.
- `skynet_countdown/config.py`, `config.toml`: validated settings and documented defaults.
- `tests/`: offline regression coverage; `examples/`: clearly labelled fictional input.

## Methodology changes

[METHODOLOGY.md](METHODOLOGY.md) governs the default 17-point calculation and 900-second starting window. Preserve the boundary between evidence judgements and Python arithmetic: the scorer must not assign totals, severity or clock movement. T3 and the autonomy amplifier require separate evidence. Relevant stories may legitimately score zero. Keep the raw source total separate from the published score, and make changes to the official defaults explicit in method metadata and documentation.

For rubric or prompt changes, include the previous behaviour, the proposed behaviour and a concrete evidence example. For calculation or pipeline changes, add focused regression coverage, including relevant boundary and failure cases. Update the documentation and configuration example when their contract changes. Reuse existing patterns and avoid introducing an abstraction for a single caller without a clear need.

A useful pull request explains the problem, resulting behaviour, verification performed and remaining limitations. Follow the repository's Lore commit convention: use an intent-led subject and appropriate git trailers such as `Tested:`, `Not-tested:` or `Constraint:`. Keep unrelated edits separate.
