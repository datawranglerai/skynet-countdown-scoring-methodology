"""Offline-evidence scorer comparisons against historical model outputs, not gold labels."""

import argparse
import json
import sys
from datetime import UTC, datetime
from hashlib import sha256
from importlib.resources import files
from pathlib import Path
from time import perf_counter
from typing import Annotated, Any, Literal, Self

from openai import OpenAI, OpenAIError
from pydantic import Field, model_validator

from .config import Config, load_config
from .llm import ChainError, run_chain
from .models import AgentRun, Assessment, Story, StrictModel, Text
from .scoring import calculate_score, remaining_seconds


class BenchmarkCase(StrictModel):
    story: Story
    reference: Assessment
    provenance: dict[str, Any]
    tags: list[Text]

    @model_validator(mode="after")
    def frozen_content_required(self) -> Self:
        if not self.story.content:
            raise ValueError("Every benchmark story needs frozen article content.")
        return self


class BenchmarkDataset(StrictModel):
    schema_version: Literal["1.0"]
    name: Text
    reference_kind: Literal["historical_model_output"]
    memory_mode: Literal["none"]
    created_at: datetime
    provenance: dict[str, Any]
    cases: Annotated[list[BenchmarkCase], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_ids(self) -> Self:
        ids = [case.story.id for case in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("Benchmark story IDs must be unique.")
        return self


def criterion_scores(assessment: Assessment) -> dict[str, int]:
    ratings = assessment.model_dump()
    return {
        f"{group}.{name}": criterion["score"]
        for group in ("trifecta", "amplifiers")
        for name, criterion in ratings[group].items()
    }


def compare_assessments(
    reference: Assessment, actual: Assessment, config: Config
) -> dict[str, Any]:
    """Positive errors mean higher candidate ratings; they do not establish incorrectness."""
    expected = criterion_scores(reference)
    observed = criterion_scores(actual)
    calculations = [
        calculate_score(item, config.scoring, config.clock, cumulative_points=0)
        for item in (reference, actual)
    ]
    baseline, candidate = calculations
    delta = candidate.total_score - baseline.total_score
    return {
        "components": {
            name: {"expected": score, "actual": observed[name], "delta": observed[name] - score}
            for name, score in expected.items()
        },
        "reference_calculation": baseline.model_dump(mode="json"),
        "actual_calculation": candidate.model_dump(mode="json"),
        "signed_total_error": delta,
        "absolute_total_error": abs(delta),
        "all_components_agree": expected == observed,
        "severity_changed": baseline.classification != candidate.classification,
        "full_trifecta_changed": baseline.full_trifecta != candidate.full_trifecta,
        "leading_indicator_changed": reference.is_leading_indicator != actual.is_leading_indicator,
    }


def _ratio(numerator: int | float, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def summarize(cases: list[dict[str, Any]], repetitions: int) -> dict[str, Any]:
    """Use explicit coverage and conditional denominators; failures never become zero scores."""
    attempts = [attempt for case in cases for attempt in case["attempts"]]
    comparisons = [
        attempt["comparison"] for attempt in attempts if attempt["comparison"] is not None
    ]
    successes = len(comparisons)
    failures = sum(attempt["error"] is not None for attempt in attempts)
    expected = len(cases) * repetitions
    names = list(criterion_scores(Assessment.model_validate(cases[0]["reference"])))
    components = {}
    for name in names:
        deltas = [comparison["components"][name]["delta"] for comparison in comparisons]
        agreements = deltas.count(0)
        components[name] = {
            "agreements": agreements,
            "agreement_rate": _ratio(agreements, successes),
            "mean_signed_delta": _ratio(sum(deltas), successes),
        }
    fully_observed = [
        case
        for case in cases
        if len(case["attempts"]) == repetitions
        and all(attempt["comparison"] is not None for attempt in case["attempts"])
    ]
    eligible = fully_observed if repetitions > 1 else []
    inconsistent_ids = []
    for case in eligible:
        signatures = {
            tuple(attempt["comparison"]["components"][name]["actual"] for name in names)
            + (attempt["assessment"]["is_leading_indicator"],)
            for attempt in case["attempts"]
        }
        if len(signatures) > 1:
            inconsistent_ids.append(case["story"]["id"])
    audits = [run for attempt in attempts for run in attempt["audit"]]
    return {
        "expected_assessments": expected,
        "successful_assessments": successes,
        "failed_assessments": failures,
        "missing_assessments": expected - successes - failures,
        "successful_assessment_coverage": _ratio(successes, expected),
        "conditional_on_successful_assessments": {
            "denominator": successes,
            "components": components,
            "all_components_agreements": sum(item["all_components_agree"] for item in comparisons),
            "all_components_agreement_rate": _ratio(
                sum(item["all_components_agree"] for item in comparisons), successes
            ),
            "mean_signed_total_error": _ratio(
                sum(item["signed_total_error"] for item in comparisons), successes
            ),
            "mean_absolute_total_error": _ratio(
                sum(item["absolute_total_error"] for item in comparisons), successes
            ),
            **{
                name: sum(item[name] for item in comparisons)
                for name in (
                    "severity_changed",
                    "full_trifecta_changed",
                    "leading_indicator_changed",
                )
            },
        },
        "repetition_consistency": {
            "total_cases": len(cases),
            "fully_observed_successful_cases": len(fully_observed),
            "cases_with_failed_or_missing_assessments": len(cases) - len(fully_observed),
            "eligible_cases_with_multiple_repetitions": len(eligible),
            "inconsistent_cases": len(inconsistent_ids),
            "inconsistent_case_rate": _ratio(len(inconsistent_ids), len(eligible)),
            "inconsistent_story_ids": inconsistent_ids,
        },
        "returned_models": sorted({run["model"] for run in audits}),
        "recorded_responses": len(audits),
        "structured_output_corrections": sum(max(0, len(item["audit"]) - 1) for item in attempts),
        "recorded_total_tokens": sum((run["usage"] or {}).get("total_tokens", 0) for run in audits),
        "responses_without_usage": sum(run["usage"] is None for run in audits),
    }


def _validate_run(
    dataset: BenchmarkDataset, config: Config, repetitions: int
) -> tuple[BenchmarkDataset, Config]:
    if isinstance(repetitions, bool) or not isinstance(repetitions, int) or repetitions < 1:
        raise ValueError("repetitions must be a positive integer.")
    dataset = BenchmarkDataset.model_validate(dataset.model_dump())
    config = Config.model_validate(config.model_dump())
    config.scorer.web_search = False
    config.write_reports = False
    config.clock.initial_evidence_points = 0
    # Ensure even the maximum configured score can be calculated before any paid calls.
    remaining_seconds(config.scoring.trifecta_points[-1] + 10, config.clock)
    return dataset, config


def _fingerprints(dataset: BenchmarkDataset, dataset_sha256: str | None) -> dict[str, Any]:
    resources = files("skynet_countdown")
    prompt = resources.joinpath("prompts", "scorer.txt").read_text("utf-8")
    return {
        "dataset_sha256": dataset_sha256 or sha256(dataset.model_dump_json().encode()).hexdigest(),
        "dataset_sha256_basis": "file_bytes" if dataset_sha256 else "model_dump_json",
        "prompt_sha256": {"scorer": sha256(prompt.encode("utf-8")).hexdigest()},
        # run_chain's source rule, arithmetic and schemas are part of the reproducible input.
        "code_sha256": {
            name: sha256(resources.joinpath(name).read_bytes()).hexdigest()
            for name in ("benchmark.py", "llm.py", "scoring.py", "models.py", "config.py")
        },
    }


def _case_means(report: dict[str, Any], config: Config) -> dict[str, Any]:
    """Validate prior attempt records and recompute means instead of trusting saved metrics."""
    repetitions = report["repetitions"]
    if type(repetitions) is not int or repetitions < 1 or not isinstance(report["cases"], list):
        raise ValueError("Invalid baseline repetitions or cases.")
    means = {}
    for case in report["cases"]:
        story_id, attempts = case["story"]["id"], case["attempts"]
        if not isinstance(story_id, str) or not story_id.strip() or story_id in means:
            raise ValueError("Baseline case IDs must be unique nonempty strings.")
        if not isinstance(attempts, list) or len(attempts) > repetitions:
            raise ValueError("Invalid baseline attempts.")
        seen, successful, failed = set(), [], 0
        for attempt in attempts:
            index, error = attempt["repetition"], attempt["error"]
            if type(index) is not int or not 1 <= index <= repetitions or index in seen:
                raise ValueError("Invalid or duplicate baseline repetition index.")
            seen.add(index)
            if error is not None and not isinstance(error, str):
                raise ValueError("Invalid baseline error record.")
            if attempt["comparison"] is not None and not isinstance(attempt["comparison"], dict):
                raise ValueError("Invalid baseline comparison record.")
            failed += error is not None
            if error is None and attempt["comparison"] is not None:
                successful.append(Assessment.model_validate(attempt["assessment"]))
        ratings = [criterion_scores(item) for item in successful]
        totals = [
            calculate_score(item, config.scoring, config.clock, cumulative_points=0).total_score
            for item in successful
        ]
        means[story_id] = {
            "expected_assessments": repetitions,
            "successful_assessments": len(successful),
            "failed_assessments": failed,
            "missing_assessments": repetitions - len(successful) - failed,
            "component_means": {
                name: sum(row[name] for row in ratings) / len(ratings) for name in ratings[0]
            }
            if ratings
            else None,
            "mean_weighted_score": _ratio(sum(totals), len(totals)),
        }
    return means


def _validate_baseline(
    baseline: Any, fingerprints: dict[str, Any], config: Config, case_ids: set[str]
) -> dict[str, Any]:
    if not isinstance(baseline, dict):
        raise ValueError("Baseline must be a benchmark report JSON object.")
    try:
        if (baseline["schema_version"], baseline["memory_mode"], baseline["reference_kind"]) != (
            "1.0",
            "none",
            "historical_model_output",
        ):
            raise ValueError(
                "Baseline must be a memory-free historical benchmark report (schema 1.0)."
            )
        if any(
            baseline[key] != fingerprints[key] for key in ("dataset_sha256", "dataset_sha256_basis")
        ):
            raise ValueError("Baseline dataset hash or hash basis differs.")
        if baseline["prompt_sha256"]["scorer"] != fingerprints["prompt_sha256"]["scorer"] or any(
            baseline["code_sha256"][name] != fingerprints["code_sha256"][name]
            for name in ("llm.py", "scoring.py", "models.py")
        ):
            raise ValueError("Baseline scorer prompt or relevant source code differs.")
        active = {"scorer", "scoring", "clock", "request_timeout_seconds", "api_max_retries"}
        settings = [
            item.model_dump(include=active)
            for item in (Config.model_validate(baseline["config"]), config)
        ]
        for item in settings:
            item["scorer"].pop("model")
        if settings[0] != settings[1]:
            raise ValueError("Baseline active settings differ beyond the scorer model.")
        means = _case_means(baseline, config)
        if not means.keys() <= case_ids:
            raise ValueError("Baseline contains story IDs outside the benchmark dataset.")
        return means
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError("Malformed baseline benchmark report.") from exc


def _compare_runs(
    current: dict[str, Any], baseline: dict[str, Any], prior: dict[str, Any], config: Config
) -> dict[str, Any]:
    cases = []
    observed_cases = _case_means(current, config)
    for story_id, observed in observed_cases.items():
        previous = prior.get(story_id)
        case = {
            "story_id": story_id,
            "baseline": previous,
            "current": observed,
            "component_mean_deltas": None,
            "weighted_score_mean_delta": None,
        }
        if previous is not None and previous["component_means"] and observed["component_means"]:
            case["component_mean_deltas"] = {
                name: value - previous["component_means"][name]
                for name, value in observed["component_means"].items()
            }
            case["weighted_score_mean_delta"] = (
                observed["mean_weighted_score"] - previous["mean_weighted_score"]
            )
        cases.append(case)
    deltas = [
        case["weighted_score_mean_delta"]
        for case in cases
        if case["weighted_score_mean_delta"] is not None
    ]
    return {
        "direction": "current minus baseline; descriptive differences, not significance tests",
        "baseline_generated_at": baseline.get("generated_at"),
        "baseline_model": Config.model_validate(baseline["config"]).scorer.model,
        "baseline_repetitions": baseline["repetitions"],
        "current_repetitions": current["repetitions"],
        "total_cases": len(cases),
        "paired_successful_cases": len(deltas),
        "unpaired_or_unusable_cases": len(cases) - len(deltas),
        "mean_weighted_score_delta_over_paired_cases": _ratio(sum(deltas), len(deltas)),
        "coverage": {
            name: {
                "expected_assessments": len(cases) * repetitions,
                "successful_assessments": sum(
                    row["successful_assessments"] for row in means.values()
                ),
                "failed_assessments": sum(row["failed_assessments"] for row in means.values()),
                "missing_assessments": sum(row["missing_assessments"] for row in means.values())
                + (len(cases) - len(means)) * repetitions,
            }
            for name, repetitions, means in (
                ("baseline", baseline["repetitions"], prior),
                ("current", current["repetitions"], observed_cases),
            )
        },
        "cases": cases,
    }


def evaluate_benchmark(
    dataset: BenchmarkDataset,
    config: Config,
    *,
    client: OpenAI,
    repetitions: int = 1,
    dataset_sha256: str | None = None,
    baseline: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Score each case independently, without relevance, retrieval, writing or prior memory."""
    supplied_config = config.model_dump(mode="json")
    dataset, config = _validate_run(dataset, config, repetitions)
    fingerprints = _fingerprints(dataset, dataset_sha256)
    prior = (
        _validate_baseline(
            baseline, fingerprints, config, {case.story.id for case in dataset.cases}
        )
        if baseline is not None
        else None
    )
    resources = files("skynet_countdown")
    prompt = resources.joinpath("prompts", "scorer.txt").read_text("utf-8")
    generated_at = datetime.now(UTC).isoformat()
    started = perf_counter()
    records = []
    for case in dataset.cases:
        record = {**case.model_dump(mode="json"), "attempts": []}
        records.append(record)
        for repetition in range(1, repetitions + 1):
            audit: list[AgentRun] = []
            attempt: dict[str, Any] = {
                "repetition": repetition,
                "assessment": None,
                "comparison": None,
                "error": None,
            }
            attempt_started = perf_counter()
            try:
                # Export metadata may contain historical ratings. Only article fields are evidence.
                actual = run_chain(
                    client,
                    instructions=prompt,
                    payload={"story": case.story.model_dump(mode="json", exclude={"metadata"})},
                    output_type=Assessment,
                    settings=config.scorer,
                    audit=audit,
                )
                attempt["assessment"] = actual.model_dump(mode="json")
                attempt["comparison"] = compare_assessments(case.reference, actual, config)
            except (ChainError, OpenAIError, ValueError) as exc:
                attempt["error"] = f"{type(exc).__name__}: {exc}"
            attempt["audit"] = [run.model_dump(mode="json") for run in audit]
            attempt["elapsed_seconds"] = perf_counter() - attempt_started
            record["attempts"].append(attempt)
    summary = summarize(records, repetitions)
    result = {
        "schema_version": "1.0",
        "reference_kind": dataset.reference_kind,
        "interpretation": "Agreement with historical model outputs; not a correctness measure.",
        "memory_mode": "none",
        "generated_at": generated_at,
        "elapsed_seconds": perf_counter() - started,
        "dataset_name": dataset.name,
        "dataset_created_at": dataset.created_at.isoformat(),
        "dataset_provenance": dataset.provenance,
        **fingerprints,
        "supplied_config": supplied_config,
        "config": config.model_dump(mode="json"),
        "repetitions": repetitions,
        "complete": summary["successful_assessments"] == summary["expected_assessments"],
        "summary": summary,
        "cases": records,
    }
    result["current_vs_baseline"] = (
        _compare_runs(result, baseline, prior, config)
        if baseline is not None and prior is not None
        else None
    )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("config.toml"))
    parser.add_argument("--output", type=Path, help="New local JSON report; never overwritten")
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--model", help="Override only the scorer model")
    parser.add_argument("--baseline", type=Path, help="Comparable prior benchmark report")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args(argv)
    if not args.validate_only and args.output is None:
        parser.error("--output is required unless --validate-only is used")
    try:
        source = args.dataset.read_bytes()
        dataset = BenchmarkDataset.model_validate_json(source.decode("utf-8-sig"))
        config = load_config(args.config)
        if args.model is not None:
            config.scorer.model = args.model
        _, effective = _validate_run(dataset, config, args.repetitions)
        baseline = (
            json.loads(args.baseline.read_text(encoding="utf-8-sig")) if args.baseline else None
        )
        if args.baseline:
            _validate_baseline(
                baseline,
                _fingerprints(dataset, sha256(source).hexdigest()),
                effective,
                {case.story.id for case in dataset.cases},
            )
        if args.validate_only:
            print(f"Valid historical baseline: {len(dataset.cases)} cases. No API calls made.")
            return 0
        # Reserve before creating a client. In particular, never overwrite the dataset itself.
        with args.output.open("x", encoding="utf-8") as output:
            try:
                with OpenAI(
                    timeout=config.request_timeout_seconds, max_retries=config.api_max_retries
                ) as client:
                    result = evaluate_benchmark(
                        dataset,
                        config,
                        client=client,
                        repetitions=args.repetitions,
                        dataset_sha256=sha256(source).hexdigest(),
                        baseline=baseline,
                    )
                json.dump(result, output, indent=2, ensure_ascii=False, allow_nan=False)
                output.write("\n")
            except BaseException:
                output.close()
                args.output.unlink(missing_ok=True)
                raise
        summary = result["summary"]
        print(
            f"Saved {args.output}: {summary['successful_assessments']} successful, "
            f"{summary['failed_assessments']} failed assessments. Historical agreement is not accuracy."
        )
        return 0 if result["complete"] else 1
    except (OSError, ValueError, OpenAIError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
