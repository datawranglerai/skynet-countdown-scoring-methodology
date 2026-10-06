"""Derive published scores and symbolic clock movements from criterion ratings."""

import math
from typing import cast

from .config import ClockConfig, ScoringConfig
from .models import Assessment, CalculatedScore, ClockMovement, Severity, StrictModel


def _validated_model[T: StrictModel](value: T, expected_type: type[T]) -> T:
    if not isinstance(value, expected_type):
        raise TypeError(f"Expected {expected_type.__name__}, got {type(value).__name__}.")
    # Also check instances changed after creation or made with model_construct().
    return expected_type.model_validate(value.model_dump())


def _validate_points(points: int) -> None:
    if isinstance(points, bool) or not isinstance(points, int) or points < 0:
        raise ValueError("Cumulative evidence points must be a nonnegative integer.")


def remaining_seconds(points: int, config: ClockConfig) -> float:
    """Return initial_seconds * 2**(-points / half_scale_points).

    The integer and fractional halvings are applied separately so that the
    exponential cannot underflow before multiplication by the initial time.
    """
    _validate_points(points)
    config = _validated_model(config, ClockConfig)
    try:
        halvings = points / config.half_scale_points
        whole_halvings = math.floor(halvings)
        seconds = math.ldexp(
            config.initial_seconds * math.exp2(-(halvings - whole_halvings)),
            -whole_halvings,
        )
    except (OverflowError, ValueError) as error:
        raise ValueError("Clock calculation exceeds floating-point precision.") from error
    if seconds == 0:
        raise ValueError(
            "Remaining time underflows floating-point precision; "
            "the mathematical clock has not reached midnight."
        )
    return seconds


def calculate_score(
    assessment: Assessment,
    scoring: ScoringConfig,
    clock: ClockConfig,
    *,
    cumulative_points: int,
) -> CalculatedScore:
    """Calculate one incident's score and its effect at the supplied baseline."""
    _validate_points(cumulative_points)
    assessment = _validated_model(assessment, Assessment)
    scoring = _validated_model(scoring, ScoringConfig)
    clock = _validated_model(clock, ClockConfig)

    active = sum(getattr(assessment.trifecta, name).score for name in ("t1", "t2", "t3"))
    trifecta_points = scoring.trifecta_points[active]
    amplifier_points = sum(
        getattr(assessment.amplifiers, name).score
        for name in type(assessment.amplifiers).model_fields
    )
    total = trifecta_points + amplifier_points
    classification: Severity = "NO MOVEMENT"
    for label, threshold in scoring.severity_thresholds.model_dump().items():
        if total >= threshold:
            classification = cast(Severity, label)

    before = remaining_seconds(cumulative_points, clock)
    after = remaining_seconds(cumulative_points + total, clock)
    percentage = -100 * math.expm1(-math.log(2) * (total / clock.half_scale_points))
    return CalculatedScore(
        trifecta_active=active,
        full_trifecta=active == 3,
        trifecta_points=trifecta_points,
        amplifier_points=amplifier_points,
        total_score=total,
        max_score=scoring.trifecta_points[3] + 10,
        classification=classification,
        clock=ClockMovement(
            cumulative_points_before=cumulative_points,
            cumulative_points_after=cumulative_points + total,
            remaining_seconds_before=before,
            remaining_seconds_after=after,
            delta_seconds=before * (percentage / 100),
            gap_closed_percent=percentage,
        ),
    )


def format_remaining_time(seconds: float) -> str:
    """Format symbolic minutes and seconds, rounded to the nearest second."""
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)):
        raise ValueError("Remaining seconds must be a finite nonnegative number.")
    try:
        valid = math.isfinite(seconds) and seconds >= 0
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError("Remaining seconds must be a finite nonnegative number.")
    minutes, whole_seconds = divmod(math.floor(seconds + 0.5), 60)
    return f"{minutes:02d}:{whole_seconds:02d}"
