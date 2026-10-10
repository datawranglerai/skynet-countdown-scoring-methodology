"""Explicit sequential evaluation: relevance, ratings, arithmetic, editorial text."""

from datetime import UTC, datetime
from hashlib import sha256
from importlib.resources import files

from openai import OpenAI, OpenAIError

from .config import Config
from .llm import ChainError, run_chain
from .models import Assessment, Dataset, Editorial, EvaluationResult, Relevance, Report, StoryResult
from .scoring import (
    calculate_score,
    evidence_pressure_percent,
    format_movement_seconds,
    format_remaining_time,
    remaining_seconds,
)


def evaluate(dataset: Dataset, config: Config, *, client: OpenAI) -> EvaluationResult:
    """Evaluate unique supplied events; failed stages are recorded and never fabricated.

    The caller owns the client and its transport retry/timeout settings. The CLI
    constructs it from config. IDs are canonical event slugs; date then ID defines
    per-incident movement. The caller supplies one selected source per event.
    """
    dataset = Dataset.model_validate(dataset.model_dump())
    config = Config.model_validate(config.model_dump())
    prompts = {
        stage: files("skynet_countdown").joinpath("prompts", stage + ".txt").read_text("utf-8")
        for stage in ("relevance", "scorer", "writer")
    }
    cumulative_points = config.clock.initial_evidence_points
    remaining_seconds(cumulative_points, config.clock)
    records = []
    for story in sorted(dataset.stories, key=lambda item: (item.published_date, item.id)):
        record = StoryResult(story=story)
        records.append(record)
        stage = "relevance"
        try:
            record.runs[stage] = []
            record.relevance = run_chain(
                client,
                instructions=prompts[stage],
                payload={"story": story.model_dump(mode="json")},
                output_type=Relevance,
                settings=config.relevance,
                audit=record.runs[stage],
            )
            if not record.relevance.relevant_to_skynet or (
                record.relevance.relevance_score < config.minimum_relevance_score
            ):
                continue
            stage = "scorer"
            record.runs[stage] = []
            record.assessment = run_chain(
                client,
                instructions=prompts[stage],
                payload={
                    "story": story.model_dump(mode="json"),
                    "relevance": record.relevance.model_dump(mode="json"),
                },
                output_type=Assessment,
                settings=config.scorer,
                audit=record.runs[stage],
            )
            stage = "calculation"
            record.calculation = calculate_score(
                record.assessment,
                config.scoring,
                config.clock,
                cumulative_points=cumulative_points,
            )
            cumulative_points = record.calculation.clock.cumulative_points_after
            record.status = "assessed"
            if not config.write_reports or (
                record.calculation.raw_source_total < config.minimum_report_score
            ):
                continue
            stage = "writer"
            record.runs[stage] = []
            editorial = run_chain(
                client,
                instructions=prompts[stage],
                payload={
                    "story": story.model_dump(mode="json"),
                    "relevance": record.relevance.model_dump(mode="json"),
                    "assessment": record.assessment.model_dump(mode="json"),
                    "calculation": record.calculation.model_dump(mode="json"),
                },
                output_type=Editorial,
                settings=config.writer,
                audit=record.runs[stage],
            )
            movement = record.calculation.clock
            record.report = Report(
                **editorial.model_dump(),
                story_id=story.id,
                severity_label=record.calculation.classification,
                clock_delta_label=format_movement_seconds(movement.delta_seconds),
                remaining_time=format_remaining_time(movement.remaining_seconds_after),
            )
            record.status = "written"
        except (ChainError, OpenAIError, ValueError) as exc:
            record.status = "error"
            record.error = f"{stage}: {exc}"

    defaults = Config()
    published_defaults = (
        config.scoring == defaults.scoring
        and config.clock.initial_seconds == defaults.clock.initial_seconds
        and config.clock.half_scale_points == defaults.clock.half_scale_points
        and config.minimum_relevance_score == defaults.minimum_relevance_score
        and config.minimum_report_score == defaults.minimum_report_score
    )
    return EvaluationResult(
        methodology_profile="published" if published_defaults else "custom",
        generated_at=datetime.now(UTC),
        config=config.model_dump(mode="json"),
        prompt_sha256={
            stage: sha256(text.encode("utf-8")).hexdigest() for stage, text in prompts.items()
        },
        cumulative_points=cumulative_points,
        remaining_seconds=remaining_seconds(cumulative_points, config.clock),
        evidence_pressure_percent=evidence_pressure_percent(cumulative_points, config.clock),
        complete=all(record.error is None for record in records),
        stories=records,
    )
