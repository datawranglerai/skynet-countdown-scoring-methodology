import itertools
import math
import unittest

from helpers import make_assessment

from skynet_countdown.config import ClockConfig, ScoringConfig, SeverityThresholds
from skynet_countdown.scoring import (
    calculate_score,
    evidence_pressure_percent,
    format_evidence_pressure,
    format_movement_seconds,
    format_remaining_time,
    gap_closed_percent,
    remaining_seconds,
)


class ScoringTests(unittest.TestCase):
    def setUp(self):
        self.scoring = ScoringConfig()
        self.clock = ClockConfig()

    def calculate(self, assessment=None, *, cumulative_points=0, scoring=None, clock=None):
        return calculate_score(
            assessment if assessment is not None else make_assessment(),
            scoring if scoring is not None else self.scoring,
            clock if clock is not None else self.clock,
            cumulative_points=cumulative_points,
        )

    def test_every_combination_of_eight_criterion_values(self):
        combinations_checked = 0
        for trifecta in itertools.product(range(2), repeat=3):
            for amplifiers in itertools.product(range(3), repeat=5):
                with self.subTest(trifecta=trifecta, amplifiers=amplifiers):
                    result = self.calculate(
                        make_assessment(trifecta, amplifiers),
                        cumulative_points=113,
                    )
                    expected_trifecta = (0, 1, 3, 7)[sum(trifecta)]
                    expected_total = expected_trifecta + sum(amplifiers)
                    self.assertEqual(result.trifecta_active, sum(trifecta))
                    self.assertEqual(result.full_trifecta, all(trifecta))
                    self.assertEqual(result.trifecta_points, expected_trifecta)
                    self.assertEqual(result.amplifier_points, sum(amplifiers))
                    self.assertEqual(result.raw_source_total, sum(trifecta) + sum(amplifiers))
                    self.assertEqual(result.total_score, expected_total)
                    self.assertEqual(result.max_score, 17)
                    self.assertEqual(
                        result.clock.cumulative_points_after,
                        113 + expected_total,
                    )
                    self.assertLessEqual(
                        result.clock.remaining_seconds_after,
                        result.clock.remaining_seconds_before,
                    )
                    combinations_checked += 1
        self.assertEqual(combinations_checked, 1944)

    def test_all_default_severity_boundaries(self):
        severities = (
            ["NO_MOVEMENT"]
            + ["CANARY"] * 2
            + ["NOTABLE"] * 2
            + ["SIGNIFICANT"] * 2
            + ["CRITICAL"] * 6
            + ["EXISTENTIAL"] * 5
        )
        for total, severity in enumerate(severities):
            with self.subTest(total=total):
                trifecta = (1, 1, 1) if total >= 7 else (0, 0, 0)
                remainder = total - (7 if total >= 7 else 0)
                amplifiers = tuple(max(0, min(2, remainder - 2 * index)) for index in range(5))
                result = self.calculate(make_assessment(trifecta, amplifiers))
                self.assertEqual(result.total_score, total)
                self.assertEqual(result.classification, severity)

    def test_full_trifecta_is_seven_points_before_amplifiers(self):
        result = self.calculate(make_assessment((1, 1, 1)))
        self.assertEqual(result.total_score, 7)
        self.assertEqual(result.classification, "CRITICAL")
        maximum = self.calculate(make_assessment((1, 1, 1), (2, 2, 2, 2, 2)))
        self.assertEqual(maximum.total_score, 17)
        self.assertEqual(maximum.classification, "EXISTENTIAL")

    def test_t3_does_not_automatically_award_an_autonomy_amplifier(self):
        t3_only = self.calculate(make_assessment((0, 0, 1)))
        autonomy_only = self.calculate(make_assessment(amplifiers=(0, 2, 0, 0, 0)))
        both = self.calculate(make_assessment((0, 0, 1), (0, 2, 0, 0, 0)))
        self.assertEqual(t3_only.total_score, 1)
        self.assertEqual(t3_only.amplifier_points, 0)
        self.assertEqual(autonomy_only.total_score, 2)
        self.assertEqual(both.total_score, 3)

    def test_leading_indicator_is_metadata_without_extra_points(self):
        assessment = make_assessment((0, 1, 0), (1, 0, 0, 0, 0))
        original = self.calculate(assessment, cumulative_points=191)
        assessment.is_leading_indicator = True
        assessment.leading_indicator_note = "An upstream constraint was removed."
        self.assertEqual(self.calculate(assessment, cumulative_points=191), original)

    def test_zero_score_preserves_the_clock(self):
        result = self.calculate(cumulative_points=113)
        self.assertEqual(result.total_score, 0)
        self.assertEqual(result.classification, "NO_MOVEMENT")
        self.assertEqual(result.clock.cumulative_points_before, 113)
        self.assertEqual(result.clock.cumulative_points_after, 113)
        self.assertEqual(
            result.clock.remaining_seconds_before,
            result.clock.remaining_seconds_after,
        )
        self.assertEqual(result.clock.delta_seconds, 0)
        self.assertEqual(result.clock.gap_closed_percent, 0)

    def test_remaining_time_formula_and_1000_point_halving(self):
        for points in (0, 1, 113, 999, 1000, 2000, 3000, 10000):
            with self.subTest(points=points):
                actual = remaining_seconds(points, self.clock)
                self.assertAlmostEqual(actual, 900 * 2 ** (-points / 1000))
                self.assertAlmostEqual(remaining_seconds(points + 1000, self.clock), actual / 2)
        self.assertEqual(remaining_seconds(0, self.clock), 900)
        self.assertEqual(remaining_seconds(1000, self.clock), 450)

    def test_reference_113_point_example(self):
        self.assertEqual(format_remaining_time(remaining_seconds(113, self.clock)), "13:52")

    def test_official_worked_examples_at_191_points(self):
        examples = (
            ((0, 0, 0), (0, 0, 0, 0, 0), 0, 0, "NO_MOVEMENT", 0.000, "13:08"),
            ((0, 1, 0), (1, 0, 0, 0, 0), 2, 2, "CANARY", 1.092, "13:07"),
            ((1, 1, 1), (0, 0, 0, 0, 0), 3, 7, "CRITICAL", 3.816, "13:05"),
            ((1, 1, 1), (0, 2, 0, 0, 0), 5, 9, "CRITICAL", 4.903, "13:03"),
            ((1, 1, 1), (2, 2, 2, 0, 0), 9, 13, "EXISTENTIAL", 7.072, "13:01"),
            ((1, 1, 1), (2, 2, 2, 2, 2), 13, 17, "EXISTENTIAL", 9.236, "12:59"),
        )
        for trifecta, amplifiers, raw, score, severity, movement, label in examples:
            with self.subTest(score=score):
                result = self.calculate(
                    make_assessment(trifecta, amplifiers), cumulative_points=191
                )
                self.assertEqual(result.raw_source_total, raw)
                self.assertEqual(result.total_score, score)
                self.assertEqual(result.classification, severity)
                self.assertAlmostEqual(result.clock.delta_seconds, movement, places=3)
                self.assertEqual(format_remaining_time(result.clock.remaining_seconds_after), label)

    def test_every_amplifier_increment_adds_one_published_point(self):
        increments_checked = 0
        for trifecta in itertools.product(range(2), repeat=3):
            for amplifiers in itertools.product(range(3), repeat=5):
                original = self.calculate(make_assessment(trifecta, amplifiers))
                for index, rating in enumerate(amplifiers):
                    if rating == 2:
                        continue
                    increased = list(amplifiers)
                    increased[index] += 1
                    result = self.calculate(make_assessment(trifecta, tuple(increased)))
                    self.assertEqual(result.total_score, original.total_score + 1)
                    increments_checked += 1
        self.assertEqual(increments_checked, 6480)

    def test_critical_and_existential_do_not_require_full_trifecta(self):
        critical = self.calculate(make_assessment(amplifiers=(2, 2, 2, 1, 0)))
        existential = self.calculate(make_assessment((1, 1, 0), (2, 2, 2, 2, 2)))
        self.assertEqual(critical.classification, "CRITICAL")
        self.assertFalse(critical.full_trifecta)
        self.assertEqual(existential.total_score, 13)
        self.assertEqual(existential.classification, "EXISTENTIAL")
        self.assertFalse(existential.full_trifecta)

    def test_incident_percentage_is_stable_while_seconds_shrink(self):
        assessment = make_assessment((1, 1, 1), (2, 2, 2, 2, 2))
        first = self.calculate(assessment)
        later = self.calculate(assessment, cumulative_points=1000)
        expected_percentage = 100 * (1 - 2 ** (-17 / 1000))
        self.assertAlmostEqual(first.clock.gap_closed_percent, expected_percentage)
        self.assertEqual(first.clock.gap_closed_percent, later.clock.gap_closed_percent)
        self.assertAlmostEqual(later.clock.delta_seconds, first.clock.delta_seconds / 2)
        self.assertAlmostEqual(
            first.clock.remaining_seconds_before - first.clock.delta_seconds,
            first.clock.remaining_seconds_after,
        )
        self.assertAlmostEqual(
            later.clock.remaining_seconds_after,
            900 * 2 ** (-1017 / 1000),
        )
        self.assertEqual(round(first.clock.gap_closed_percent, 2), 1.17)
        two_points = self.calculate(make_assessment(amplifiers=(2, 0, 0, 0, 0)))
        self.assertEqual(round(two_points.clock.gap_closed_percent, 2), 0.14)

    def test_custom_weights_and_thresholds_determine_severity_without_override(self):
        scoring = ScoringConfig(
            trifecta_points=[0, 2, 5, 11],
            severity_thresholds=SeverityThresholds(
                CANARY=1,
                NOTABLE=4,
                SIGNIFICANT=8,
                CRITICAL=12,
                EXISTENTIAL=19,
            ),
        )
        full_trifecta = self.calculate(make_assessment((1, 1, 1)), scoring=scoring)
        self.assertEqual(full_trifecta.total_score, 11)
        self.assertEqual(full_trifecta.max_score, 21)
        self.assertEqual(full_trifecta.classification, "SIGNIFICANT")
        amplified = self.calculate(
            make_assessment((1, 1, 1), (2, 0, 0, 0, 0)),
            scoring=scoring,
        )
        self.assertEqual(amplified.total_score, 13)
        self.assertEqual(amplified.classification, "CRITICAL")

    def test_custom_clock_constants_and_explicit_baseline(self):
        clock = ClockConfig(
            initial_seconds=7200,
            half_scale_points=200,
            initial_evidence_points=23,
        )
        self.assertEqual(remaining_seconds(0, clock), 7200)
        self.assertEqual(remaining_seconds(200, clock), 3600)
        result = self.calculate(
            make_assessment((1, 1, 1)),
            cumulative_points=200,
            clock=clock,
        )
        self.assertEqual(result.clock.cumulative_points_after, 207)
        self.assertAlmostEqual(result.clock.remaining_seconds_after, 7200 * 2 ** (-207 / 200))
        self.assertAlmostEqual(
            result.clock.gap_closed_percent,
            -100 * math.expm1(-math.log(2) * 7 / 200),
        )

    def test_public_calculators_reject_invalid_evidence_counts(self):
        for points in (
            -1,
            True,
            False,
            1.0,
            "1",
            None,
            math.nan,
            math.inf,
            -math.inf,
            2**53,
            10**400,
        ):
            with self.subTest(points=points):
                with self.assertRaises(ValueError):
                    remaining_seconds(points, self.clock)
                with self.assertRaises(ValueError):
                    self.calculate(cumulative_points=points)

    def test_public_calculators_validate_models_even_after_mutation(self):
        invalid_clock = self.clock.model_copy(update={"half_scale_points": 0})
        invalid_scoring = self.scoring.model_copy(
            update={"trifecta_points": [0, 1, 3, -7]},
        )
        invalid_assessment = make_assessment()
        invalid_assessment.trifecta.t1.score = 2
        with self.assertRaises(ValueError):
            remaining_seconds(0, invalid_clock)
        with self.assertRaises(ValueError):
            self.calculate(clock=invalid_clock)
        with self.assertRaises(ValueError):
            self.calculate(scoring=invalid_scoring)
        with self.assertRaises(ValueError):
            self.calculate(invalid_assessment)
        with self.assertRaises(TypeError):
            remaining_seconds(0, {})
        with self.assertRaises(TypeError):
            calculate_score({}, self.scoring, self.clock, cumulative_points=0)
        with self.assertRaises(TypeError):
            calculate_score(make_assessment(), {}, self.clock, cumulative_points=0)

    def test_underflow_retains_positive_time_and_movement(self):
        for points in (10_000_000, 2**53 - 1):
            with self.subTest(points=points):
                self.assertEqual(remaining_seconds(points, self.clock), math.ulp(0.0))
        tiny_clock = ClockConfig(initial_seconds=math.ulp(0.0), half_scale_points=1)
        positive = self.calculate(make_assessment((1, 0, 0)), clock=tiny_clock)
        self.assertEqual(positive.clock.remaining_seconds_after, math.ulp(0.0))
        self.assertGreater(positive.clock.delta_seconds, 0)
        zero = self.calculate(clock=tiny_clock)
        self.assertEqual(zero.clock.delta_seconds, 0)
        tiny_half_scale = ClockConfig(half_scale_points=math.ulp(0.0))
        self.assertEqual(remaining_seconds(1, tiny_half_scale), math.ulp(0.0))

    def test_cumulative_total_cannot_exceed_safe_integer_limit(self):
        with self.assertRaises(ValueError):
            self.calculate(make_assessment((1, 0, 0)), cumulative_points=2**53 - 1)

    def test_pressure_and_gap_shares_use_fixed_sensitivity(self):
        for points, display in ((0, "0.0"), (113, "7.5"), (191, "12.4"), (1000, "50.0")):
            with self.subTest(points=points):
                actual = evidence_pressure_percent(points, self.clock)
                self.assertAlmostEqual(actual, 100 * (1 - 2 ** (-points / 1000)))
                self.assertEqual(format_evidence_pressure(actual), display)
        self.assertEqual(evidence_pressure_percent(2000, self.clock), 75)
        self.assertEqual(
            format_evidence_pressure(evidence_pressure_percent(10_000_000, self.clock)), "<100"
        )
        custom = ClockConfig(initial_seconds=1, half_scale_points=200)
        self.assertEqual(evidence_pressure_percent(200, custom), 50)
        self.assertEqual(gap_closed_percent(200, custom), 50)
        self.assertAlmostEqual(gap_closed_percent(9, self.clock), 0.62189067, places=8)
        self.assertGreater(gap_closed_percent(1, ClockConfig(half_scale_points=1e308)), 0)
        for invalid in (-1, True, 1.0, math.nan, math.inf, 2**53):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                evidence_pressure_percent(invalid, self.clock)

    def test_pressure_display_cannot_claim_complete_loss_of_the_symbolic_gap(self):
        for percentage, display in ((0, "0.0"), (99.94, "99.9"), (99.95, "<100"), (100, "<100")):
            with self.subTest(percentage=percentage):
                self.assertEqual(format_evidence_pressure(percentage), display)
        for invalid in (-1, 101, True, None, "50", math.inf, math.nan, 10**400):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                format_evidence_pressure(invalid)

    def test_movement_display_keeps_positive_values_distinct_from_zero(self):
        for seconds, display in (
            (0, "NO MOVEMENT"),
            (math.ulp(0.0), "<1 SECOND CLOSER"),
            (0.001, "<1 SECOND CLOSER"),
            (0.999, "<1 SECOND CLOSER"),
            (1, "1.00 SECONDS CLOSER"),
            (4.903, "4.90 SECONDS CLOSER"),
        ):
            with self.subTest(seconds=seconds):
                self.assertEqual(format_movement_seconds(seconds), display)
        for invalid in (-1, True, None, "1", math.inf, math.nan):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                format_movement_seconds(invalid)

    def test_large_initial_time_avoids_intermediate_exponential_underflow(self):
        clock = ClockConfig(initial_seconds=1e300, half_scale_points=1)
        actual = remaining_seconds(1500, clock)
        self.assertEqual(actual, math.ldexp(1e300, -1500))
        self.assertGreater(actual, 0)

    def test_large_initial_time_avoids_intermediate_delta_overflow(self):
        clock = ClockConfig(initial_seconds=1e308, half_scale_points=1)
        result = self.calculate(
            make_assessment((1, 1, 1), (2, 2, 2, 2, 2)),
            clock=clock,
        )
        self.assertTrue(math.isfinite(result.clock.delta_seconds))
        self.assertTrue(math.isclose(result.clock.delta_seconds, 1e308 * (1 - 2**-17)))

    def test_small_movement_uses_expm1_instead_of_subtracting_near_equals(self):
        clock = ClockConfig(half_scale_points=1e20)
        result = self.calculate(make_assessment((1, 0, 0)), clock=clock)
        self.assertEqual(1 - 2 ** (-1 / 1e20), 0)
        self.assertGreater(result.clock.gap_closed_percent, 0)
        self.assertGreater(result.clock.delta_seconds, 0)
        self.assertAlmostEqual(
            result.clock.gap_closed_percent / (100 * math.log(2) / 1e20),
            1,
        )

    def test_symbolic_display_uses_minutes_and_rounds_nearest_second(self):
        for seconds, expected in (
            (0, "<00:01"),
            (math.ulp(0.0), "<00:01"),
            (0.4, "<00:01"),
            (0.5, "<00:01"),
            (0.999, "<00:01"),
            (1, "00:01"),
            (59.5, "01:00"),
            (60, "01:00"),
            (3599.5, "60:00"),
            (3600, "60:00"),
            (7200, "120:00"),
        ):
            with self.subTest(seconds=seconds):
                self.assertEqual(format_remaining_time(seconds), expected)

    def test_symbolic_display_rejects_invalid_inputs(self):
        for seconds in (-1, True, False, None, "1", math.inf, -math.inf, math.nan, 10**400):
            with self.subTest(seconds=seconds):
                with self.assertRaises(ValueError):
                    format_remaining_time(seconds)


if __name__ == "__main__":
    unittest.main()
