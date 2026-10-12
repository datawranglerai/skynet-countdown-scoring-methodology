# Development and documentation

Work from a Python 3.13+ checkout. `uv sync` installs the dependencies declared in `pyproject.toml`; the scoring pipeline, local benchmark and documentation site share that environment.

## Project layout

```text
skynet_countdown/
  __main__.py       Assessment command
  pipeline.py       Stage ordering and failure isolation
  llm.py            Structured model requests and correction attempts
  models.py         Validated data contracts
  scoring.py        Pure scoring and clock functions
  config.py         TOML configuration and published defaults
  benchmark.py      Independent scorer runs and saved-run comparison
  prompts/         Relevance, assessment and writing instructions
tests/             Offline regression tests
examples/          Fictional input and frozen benchmark fixtures
docs/              Documentation source
docs_theme/        Static repository-link theme override
mkdocs.yml         Site navigation, theme and validation
```

The [component reference](components.md) explains how these boundaries fit together. The [methodology](methodology.md) is the scoring authority; root `METHODOLOGY.md` points to it.

## Run the offline checks

```sh
uv run python -m skynet_countdown --input examples/stories.json --validate-only
uv run python -m skynet_countdown.benchmark --dataset examples/benchmarks/benchmark.json --validate-only
uv run python -m unittest discover -s tests -v
uv run python -m compileall -q skynet_countdown
```

Validation and unit tests do not make model calls. The tests use modelled API responses to exercise the same structured-output boundary used by live runs. Arithmetic coverage includes every valid combination of the eight ratings, severity boundaries, worked clock examples and numerical edge cases. Pipeline tests cover ordering, gates, output handling and partial failures. Benchmark tests cover reference isolation, repeat independence, saved-run compatibility and failure accounting; fixture tests check the link between frozen evidence, source provenance and historical ratings.

If Ruff and mypy are available as development tools, run:

```sh
ruff check skynet_countdown tests
mypy skynet_countdown tests/test_benchmark.py tests/test_benchmark_data.py
```

They are not project runtime dependencies. Some older negative-test fixtures intentionally violate type signatures and are not part of this mypy target. Keep live model evaluation separate from offline unit tests and record model settings with any reported result.

## Make a focused change

| Change | Evidence to include |
| --- | --- |
| Rubric or prompt | A concrete evidence example, expected interpretation and benchmark differences. |
| Scoring calculation | Boundary cases, the methodology rationale and focused arithmetic regressions. |
| Pipeline or schema | Stage/failure tests and any output-contract changes. |
| Benchmark dataset | Source provenance, a review rationale, updated hashes and a new baseline. |
| Model selection | Compatible saved-run comparisons, repeat variability and reviewed disagreements. |
| Documentation | A strict build and a check that examples describe the implemented behaviour. |

Keep ratings and arithmetic separate. Reuse the existing contracts and pure functions; introduce a dependency only when a concrete need justifies it. Preserve explicit failures and output-file protection. Changes to prompts, contracts and relevant source files can intentionally make an old benchmark report incompatible; [the benchmark guide](benchmarking.md) explains when to establish a new baseline.

Commit messages should explain the reason for a change. Useful native Git trailers include `Tested:`, `Not-tested:`, `Constraint:` and `Directive:`. Put the verification and known limits in the change description so a reviewer can assess the outcome without the development conversation.

## Preview the documentation

MkDocs and Material for MkDocs are already declared in the project environment:

```sh
uv run mkdocs serve
```

Open **http://127.0.0.1:8000**. MkDocs watches the Markdown and configuration files and rebuilds when they change. To use another port:

```sh
uv run mkdocs serve --dev-addr 127.0.0.1:8001
```

The site uses Material's navigation, local search index, code-copy buttons and light/dark palettes. Fonts are system fonts. A small theme override keeps the repository link static, without fetching release statistics. Mermaid diagrams use Material's built-in renderer, which loads its runtime from a CDN; explanatory text and component tables remain readable without it. See [Material's diagram documentation](https://squidfunk.github.io/mkdocs-material/reference/diagrams/) for the rendering configuration.

## Build and publish

```sh
uv run mkdocs build --strict
```

The static output is written to `site/`, which is ignored by Git. Missing pages, links and anchors fail the strict build. The [MkDocs configuration guide](https://www.mkdocs.org/user-guide/configuration/) describes these checks. Browser verification also matters: check navigation, search, diagrams and narrow-screen tables after changing layout or theme settings.

`docs/` is the publication boundary. Data exports, generated assessment reports, local acquisition caches and credentials are not copied into the site. Use relative links between Markdown pages; repository paths outside `docs/` should be written as code paths or deliberate repository links.

The output can be hosted by any static web server. No deployment workflow or hosting account is configured by this change. When choosing a host, configure its final base URL as `site_url` in `mkdocs.yml`, publish the contents of `site/`, and run the strict build in that host's build job. Keep preview/build work independent from model API calls.
