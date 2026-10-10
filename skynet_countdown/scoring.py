"""Derive published scores and symbolic clock movements from criterion ratings."""

import math
from typing import cast

from .config import ClockConfig, ScoringConfig
from .models import (
    MAX_SAFE_EVIDENCE_POINTS,
    Assessment,
    CalculatedScore,
    ClockMovement,
    Severity,
    StrictModel,
)

MIN_POSITIVE_SECONDS = math.ulp(0.0)


def _validated_model[T: StrictModel](value: T, expected_type: type[T]) -> T:
    if not isinstance(value, expected_type):
        raise TypeError(f"Expected {expected_type.__name__}, got {type(value).__name__}.")
    # Also check instances changed after creation or made with model_construct().
    return expected_type.model_validate(value.model_dump())


def _validate_points(points: int) -> None:
    if (
        isinstance(points, bool)
        or not isinstance(points, int)
        or not 0 <= points <= MAX_SAFE_EVIDENCE_POINTS
    ):
        raise ValueError("Evidence points must be a nonnegative safe integer (at most 2**53 - 1).")


def _gap_fraction(points: int, config: ClockConfig) -> float:
    if points == 0:
        return 0.0
    return -math.expm1(-math.log(2) * (points / config.half_scale_points))


def gap_closed_percent(score: int, config: ClockConfig) -> float:
    """Return an incident's stable percentage of the remaining symbolic gap."""
    _validate_points(score)
    config = _validated_model(config, ClockConfig)
    return 100 * _gap_fraction(score, config)


def evidence_pressure_percent(points: int, config: ClockConfig) -> float:
    """Return the percentage of the initial window consumed by cumulative evidence."""
    return gap_closed_percent(points, config)


def remaining_seconds(points: int, config: ClockConfig) -> float:
    """Return initial_seconds * 2**(-points / half_scale_points).

    The integer and fractional halvings are applied separately so that the
    exponential cannot underflow before multiplication by the initial time.
    """
    _validate_points(points)
    config = _validated_model(config, ClockConfig)
    halvings = points / config.half_scale_points
    if math.isinf(halvings):
        return MIN_POSITIVE_SECONDS
    try:
        whole_halvings = math.floor(halvings)
        seconds = math.ldexp(
            config.initial_seconds * math.exp2(-(halvings - whole_halvings)),
            -whole_halvings,
        )
    except OverflowError:
        # An exponent beyond ldexp's integer range can only underflow here.
        return MIN_POSITIVE_SECONDS
    return max(MIN_POSITIVE_SECONDS, seconds)


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
    classification: Severity = "NO_MOVEMENT"
    for label, threshold in scoring.severity_thresholds.model_dump().items():
        if total >= threshold:
            classification = cast(Severity, label)

    before = remaining_seconds(cumulative_points, clock)
    after = remaining_seconds(cumulative_points + total, clock)
    fraction = _gap_fraction(total, clock)
    return CalculatedScore(
        trifecta_active=active,
        full_trifecta=active == 3,
        trifecta_points=trifecta_points,
        amplifier_points=amplifier_points,
        raw_source_total=active + amplifier_points,
        total_score=total,
        max_score=scoring.trifecta_points[3] + 10,
        classification=classification,
        clock=ClockMovement(
            cumulative_points_before=cumulative_points,
            cumulative_points_after=cumulative_points + total,
            remaining_seconds_before=before,
            remaining_seconds_after=after,
            delta_seconds=0 if total == 0 else max(MIN_POSITIVE_SECONDS, before * fraction),
            gap_closed_percent=100 * fraction,
        ),
    )


def _validate_seconds(seconds: float) -> None:
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)):
        raise ValueError("Remaining seconds must be a finite nonnegative number.")
    try:
        valid = math.isfinite(seconds) and seconds >= 0
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError("Remaining seconds must be a finite nonnegative number.")


def format_remaining_time(seconds: float) -> str:
    """Round symbolic time to seconds, preserving the positive sub-second interval."""
    _validate_seconds(seconds)
    if seconds < 1:
        return "<00:01"
    minutes, whole_seconds = divmod(math.floor(seconds + 0.5), 60)
    return f"{minutes:02d}:{whole_seconds:02d}"


def format_evidence_pressure(percentage: float) -> str:
    """Display cumulative pressure to one decimal without claiming midnight."""
    if isinstance(percentage, bool) or not isinstance(percentage, (int, float)):
        raise ValueError("Evidence pressure must be a finite number from 0 to 100.")
    try:
        valid = math.isfinite(percentage) and 0 <= percentage <= 100
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError("Evidence pressure must be a finite number from 0 to 100.")
    return "<100" if percentage >= 99.95 else f"{percentage:.1f}"


def format_movement_seconds(seconds: float) -> str:
    """Keep exact zero and positive sub-second incident movements distinct."""
    _validate_seconds(seconds)
    if seconds == 0:
        return "NO MOVEMENT"
    if seconds < 1:
        return "<1 SECOND CLOSER"
    return f"{seconds:.2f} SECONDS CLOSER"
