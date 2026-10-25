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
    """Revalidate a model's fields, including changes made after construction.

    :param value: Model instance to validate.
    :type value: T
    :param expected_type: Required model class and validation schema.
    :type expected_type: type[T]
    :return: A newly validated instance of the expected model class.
    :rtype: T
    :raises TypeError: If ``value`` is not an instance of ``expected_type``.
    :raises pydantic.ValidationError: If the model's fields are invalid.
    """
    if not isinstance(value, expected_type):
        raise TypeError(f"Expected {expected_type.__name__}, got {type(value).__name__}.")
    # Also check instances changed after creation or made with model_construct().
    return expected_type.model_validate(value.model_dump())


def _validate_points(points: int) -> None:
    """Check that an evidence count is a nonnegative safe integer.

    :param points: Evidence count to check; booleans are not accepted.
    :type points: int
    :return: ``None`` if the evidence count is valid.
    :rtype: None
    :raises ValueError: If ``points`` is not an integer from zero to
        ``MAX_SAFE_EVIDENCE_POINTS``, inclusive, or is a boolean.
    """
    if (
        isinstance(points, bool)
        or not isinstance(points, int)
        or not 0 <= points <= MAX_SAFE_EVIDENCE_POINTS
    ):
        raise ValueError("Evidence points must be a nonnegative safe integer (at most 2**53 - 1).")


def _gap_fraction(points: int, config: ClockConfig) -> float:
    """Compute the fraction of the symbolic gap closed by validated points.

    :param points: Previously validated nonnegative evidence count.
    :type points: int
    :param config: Previously validated clock settings defining the halving scale.
    :type config: ClockConfig
    :return: ``1 - 2**(-points / half_scale_points)``, computed with ``expm1``
        to preserve precision for small fractions.
    :rtype: float
    """
    if points == 0:
        return 0.0
    return -math.expm1(-math.log(2) * (points / config.half_scale_points))


def gap_closed_percent(score: int, config: ClockConfig) -> float:
    """Return an incident's stable percentage of the remaining symbolic gap.

    :param score: Nonnegative safe integer score for one incident.
    :type score: int
    :param config: Clock settings defining the halving scale.
    :type config: ClockConfig
    :return: Percentage of the remaining gap closed, independent of prior points.
    :rtype: float
    :raises ValueError: If ``score`` is not a nonnegative safe integer or is a boolean.
    :raises TypeError: If ``config`` is not a ``ClockConfig`` instance.
    :raises pydantic.ValidationError: If the clock settings are invalid.
    """
    _validate_points(score)
    config = _validated_model(config, ClockConfig)
    return 100 * _gap_fraction(score, config)


def evidence_pressure_percent(points: int, config: ClockConfig) -> float:
    """Return the percentage of the initial window consumed by cumulative evidence.

    :param points: Cumulative evidence count as a nonnegative safe integer.
    :type points: int
    :param config: Clock settings defining the halving scale.
    :type config: ClockConfig
    :return: Cumulative pressure from zero to 100; floating-point rounding can
        produce 100 even while symbolic time remains positive.
    :rtype: float
    :raises ValueError: If ``points`` is not a nonnegative safe integer or is a boolean.
    :raises TypeError: If ``config`` is not a ``ClockConfig`` instance.
    :raises pydantic.ValidationError: If the clock settings are invalid.
    """
    return gap_closed_percent(points, config)


def remaining_seconds(points: int, config: ClockConfig) -> float:
    """Return ``initial_seconds * 2**(-points / half_scale_points)``.

    The integer and fractional halvings are applied separately so that the
    exponential cannot underflow before multiplication by the initial time.

    :param points: Cumulative evidence count as a nonnegative safe integer.
    :type points: int
    :param config: Clock settings defining the initial time and halving scale.
    :type config: ClockConfig
    :return: Remaining symbolic seconds, floored at the smallest positive float
        so that underflow never produces zero.
    :rtype: float
    :raises ValueError: If ``points`` is not a nonnegative safe integer or is a boolean.
    :raises TypeError: If ``config`` is not a ``ClockConfig`` instance.
    :raises pydantic.ValidationError: If the clock settings are invalid.
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
    """Calculate one incident's score and its effect at the supplied baseline.

    The published score combines the configured Trifecta points with amplifier
    ratings. The raw source total uses the count of active Trifecta criteria
    instead. Leading-indicator metadata does not contribute points.

    :param assessment: Criterion ratings and supporting judgements for the incident.
    :type assessment: Assessment
    :param scoring: Trifecta point lookup and severity thresholds.
    :type scoring: ScoringConfig
    :param clock: Initial time and evidence-to-time halving settings.
    :type clock: ClockConfig
    :param cumulative_points: Evidence count before this incident, supplied explicitly.
    :type cumulative_points: int
    :return: Score components, severity and clock movement before and after the incident.
    :rtype: CalculatedScore
    :raises ValueError: If the baseline or updated cumulative count is outside the
        nonnegative safe integer range, or the baseline is not an integer or is a boolean.
    :raises TypeError: If a model argument is not an instance of its required class.
    :raises pydantic.ValidationError: If assessment or configuration fields are invalid.
    """
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
    """Check that a duration is finite and nonnegative.

    :param seconds: Duration to check; booleans are not accepted.
    :type seconds: float or int
    :return: ``None`` if the duration is valid.
    :rtype: None
    :raises ValueError: If ``seconds`` is not a finite nonnegative number, is a
        boolean, or is too large to check as a float.
    """
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)):
        raise ValueError("Remaining seconds must be a finite nonnegative number.")
    try:
        valid = math.isfinite(seconds) and seconds >= 0
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError("Remaining seconds must be a finite nonnegative number.")


def format_remaining_time(seconds: float) -> str:
    """Format symbolic time as total minutes and rounded seconds.

    :param seconds: Finite nonnegative remaining duration in seconds.
    :type seconds: float or int
    :return: ``<00:01`` for any value below one second, including zero; otherwise
        ``MM:SS``, rounded to the nearest second with halves rounded up.
    :rtype: str
    :raises ValueError: If ``seconds`` is not a finite nonnegative number, is a
        boolean, or is too large to check as a float.
    """
    _validate_seconds(seconds)
    if seconds < 1:
        return "<00:01"
    minutes, whole_seconds = divmod(math.floor(seconds + 0.5), 60)
    return f"{minutes:02d}:{whole_seconds:02d}"


def format_evidence_pressure(percentage: float) -> str:
    """Display cumulative pressure to one decimal without claiming midnight.

    :param percentage: Finite cumulative pressure from zero to 100, inclusive.
    :type percentage: float or int
    :return: ``<100`` for values at least 99.95; otherwise a value with one
        decimal place. Neither form includes a percent sign.
    :rtype: str
    :raises ValueError: If ``percentage`` is not a finite number in the accepted
        range or is a boolean.
    """
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
    """Keep exact zero and positive sub-second incident movements distinct.

    :param seconds: Finite nonnegative movement towards midnight in seconds.
    :type seconds: float or int
    :return: ``NO MOVEMENT`` for zero, ``<1 SECOND CLOSER`` below one second,
        or a duration with two decimal places followed by ``SECONDS CLOSER``.
    :rtype: str
    :raises ValueError: If ``seconds`` is not a finite nonnegative number, is a
        boolean, or is too large to check as a float.
    """
    _validate_seconds(seconds)
    if seconds == 0:
        return "NO MOVEMENT"
    if seconds < 1:
        return "<1 SECOND CLOSER"
    return f"{seconds:.2f} SECONDS CLOSER"
