import unittest
from datetime import date

from skynet_countdown.config import Config
from skynet_countdown.models import Dataset, EvaluationResult, Story
from skynet_countdown.pipeline import evaluate
from skynet_countdown.scoring import evidence_pressure_percent, remaining_seconds
from tests.fakes import editorial, fake_client, make_response, relevance
from tests.helpers import make_assessment


def story(identifier: str, day: int = 1) -> Story:
    return Story(
        id=identifier,
        title=f"Fictional story {identifier}",
        source_url=f"https://example.com/{identifier}",
        published_date=date(2026, 9, day),
        summary="Fictional evidence supplied for a test.",
        content="Additional supplied source text.",
        metadata={"fictional": True},
    )


class PipelineTests(unittest.TestCase):
    def test_full_pipeline_retains_excluded_and_low_scoring_stories(self):
        dataset = Dataset(stories=[story("excluded", 3), story("high", 2), story("low", 1)])
        low = make_assessment((0, 0, 1)).model_dump()
        high = make_assessment((1, 1, 1), (1, 0, 0, 0, 0)).model_dump()
        high["is_leading_indicator"] = True
        high["leading_indicator_note"] = "An oversight constraint was removed."
        client = fake_client(relevance(), low, relevance(), high, editorial(), relevance(False, 1))
        result = evaluate(dataset, Config(), client=client)
        self.assertTrue(result.complete)
        self.assertEqual(result.schema_version, "2.0")
        self.assertEqual(result.methodology_version, "1.0")
        self.assertEqual(result.calibration_effective_date, date(2026, 10, 7))
        self.assertEqual(result.methodology_profile, "published")
        self.assertEqual([r.story.id for r in result.stories], ["low", "high", "excluded"])
        self.assertEqual([r.status for r in result.stories], ["assessed", "written", "excluded"])
        self.assertEqual(result.cumulative_points, 9)
        self.assertAlmostEqual(result.remaining_seconds, remaining_seconds(9, Config().clock))
        low_record, high_record, excluded = result.stories
        self.assertEqual(low_record.calculation.total_score, 1)
        self.assertIsNone(low_record.report)
        self.assertEqual(high_record.calculation.total_score, 8)
        self.assertEqual(high_record.calculation.classification, "CRITICAL")
        self.assertEqual(high_record.calculation.clock.cumulative_points_before, 1)
        self.assertEqual(high_record.report.story_id, "high")
        self.assertEqual(high_record.report.severity_label, "CRITICAL")
        self.assertEqual(high_record.story, dataset.stories[1])
        self.assertIsNone(excluded.assessment)
        writer_request = client.responses.create.call_args_list[4].kwargs
        self.assertIn("An oversight constraint was removed.", writer_request["input"][0]["content"])
        self.assertIn('"total_score": 8', writer_request["input"][0]["content"])
        self.assertEqual(len(result.prompt_sha256), 3)
        self.assertTrue(all(len(value) == 64 for value in result.prompt_sha256.values()))
        self.assertEqual(EvaluationResult.model_validate_json(result.model_dump_json()), result)

    def test_equal_dates_use_stable_event_ids(self):
        dataset = Dataset(stories=[story("z"), story("a")])
        client = fake_client(relevance(False, 1), relevance(False, 1))
        result = evaluate(dataset, Config(), client=client)
        self.assertEqual([r.story.id for r in result.stories], ["a", "z"])

    def test_editorial_threshold_uses_raw_total_without_filtering_assessments(self):
        client = fake_client(relevance(), make_assessment((1, 1, 1)).model_dump())
        result = evaluate(
            Dataset(stories=[story("full-trifecta")]),
            Config(minimum_report_score=4),
            client=client,
        )
        record = result.stories[0]
        self.assertTrue(result.complete)
        self.assertEqual(record.status, "assessed")
        self.assertEqual(record.calculation.raw_source_total, 3)
        self.assertEqual(record.calculation.total_score, 7)
        self.assertEqual(result.cumulative_points, 7)
        self.assertIsNone(record.report)
        self.assertEqual(client.responses.create.call_count, 2)

    def test_contradictory_relevance_is_corrected_before_scoring(self):
        client = fake_client(relevance(True, 2), relevance(False, 2))
        result = evaluate(Dataset(stories=[story("excluded")]), Config(), client=client)
        self.assertTrue(result.complete)
        self.assertEqual(result.stories[0].status, "excluded")
        self.assertIsNone(result.stories[0].assessment)
        self.assertEqual(result.cumulative_points, 0)
        self.assertNotIn("scorer", result.stories[0].runs)
        self.assertEqual(len(result.stories[0].runs["relevance"]), 2)

    def test_same_date_input_permutations_preserve_per_event_movement(self):
        assessment = make_assessment((1, 1, 1)).model_dump()
        results = []
        for identifiers in (("z", "a"), ("a", "z")):
            client = fake_client(relevance(), assessment, relevance(), assessment)
            result = evaluate(
                Dataset(stories=[story(identifier) for identifier in identifiers]),
                Config(write_reports=False),
                client=client,
            )
            results.append(
                [(record.story.id, record.calculation.clock) for record in result.stories]
            )
        self.assertEqual(results[0], results[1])

    def test_relevance_threshold_and_flag_are_both_required(self):
        client = fake_client(relevance(True, 4), relevance(False, 9))
        result = evaluate(
            Dataset(stories=[story("borderline"), story("irrelevant")]),
            Config(minimum_relevance_score=5),
            client=client,
        )
        self.assertEqual(client.responses.create.call_count, 2)
        self.assertEqual(result.cumulative_points, 0)
        self.assertTrue(all(r.assessment is None for r in result.stories))

    def test_zero_context_can_be_written_without_clock_movement(self):
        client = fake_client(relevance(), make_assessment().model_dump(), editorial())
        result = evaluate(
            Dataset(stories=[story("zero")]),
            Config(minimum_report_score=0),
            client=client,
        )
        record = result.stories[0]
        self.assertEqual(record.report.severity_label, "NO_MOVEMENT")
        self.assertEqual(record.report.clock_delta_label, "NO MOVEMENT")
        self.assertEqual(record.report.remaining_time, "15:00")
        self.assertEqual(record.calculation.clock.delta_seconds, 0.0)

    def test_reports_disabled_still_accumulates_points_from_seed(self):
        config = Config(write_reports=False)
        config.clock.initial_evidence_points = 1000
        client = fake_client(relevance(), make_assessment((1, 1, 1)).model_dump())
        result = evaluate(Dataset(stories=[story("scored")]), config, client=client)
        self.assertEqual(result.cumulative_points, 1007)
        self.assertEqual(result.stories[0].calculation.clock.remaining_seconds_before, 450.0)
        self.assertEqual(result.stories[0].status, "assessed")
        self.assertEqual(client.responses.create.call_count, 2)
        self.assertEqual(result.methodology_profile, "published")
        self.assertEqual(
            result.evidence_pressure_percent, evidence_pressure_percent(1007, config.clock)
        )

    def test_custom_constants_are_marked_as_a_methodology_variant(self):
        for config in (
            Config(clock={"initial_seconds": 3600}),
            Config(clock={"half_scale_points": 200}),
            Config(scoring={"trifecta_points": [0, 2, 4, 8]}),
            Config(scoring={"severity_thresholds": {"EXISTENTIAL": 14}}),
            Config(minimum_relevance_score=5),
            Config(minimum_report_score=4),
        ):
            with self.subTest(config=config):
                result = evaluate(Dataset(stories=[]), config, client=fake_client())
                self.assertEqual(result.methodology_profile, "custom")

    def test_positive_subsecond_report_does_not_claim_zero_or_midnight(self):
        config = Config(clock={"initial_seconds": 0.1})
        client = fake_client(relevance(), make_assessment((1, 1, 1)).model_dump(), editorial())
        result = evaluate(Dataset(stories=[story("tiny")]), config, client=client)
        self.assertTrue(result.complete)
        self.assertGreater(result.stories[0].calculation.clock.delta_seconds, 0)
        self.assertEqual(result.stories[0].report.clock_delta_label, "<1 SECOND CLOSER")
        self.assertEqual(result.stories[0].report.remaining_time, "<00:01")

    def test_writer_failure_retains_assessment_and_later_story_runs(self):
        refused = make_response(
            "",
            output=[
                {
                    "id": "msg_refusal",
                    "type": "message",
                    "role": "assistant",
                    "status": "completed",
                    "content": [{"type": "refusal", "refusal": "Cannot write this report."}],
                }
            ],
        )
        client = fake_client(
            relevance(),
            make_assessment((1, 1, 1)).model_dump(),
            refused,
            relevance(False, 1),
        )
        result = evaluate(
            Dataset(stories=[story("failed"), story("later")]), Config(), client=client
        )
        self.assertFalse(result.complete)
        self.assertEqual(result.cumulative_points, 7)
        self.assertEqual(result.stories[0].status, "error")
        self.assertIn("writer:", result.stories[0].error)
        self.assertIsNotNone(result.stories[0].assessment)
        self.assertIsNone(result.stories[0].report)
        self.assertEqual(result.stories[1].status, "excluded")

    def test_incomplete_scorer_never_contributes_points(self):
        incomplete = make_response(
            make_assessment((1, 1, 1)).model_dump(),
            status="incomplete",
            incomplete_details={"reason": "max_output_tokens"},
        )
        client = fake_client(relevance(), incomplete)
        result = evaluate(Dataset(stories=[story("failed")]), Config(), client=client)
        self.assertEqual(result.cumulative_points, 0)
        self.assertIsNone(result.stories[0].assessment)
        self.assertIn("scorer:", result.stories[0].error)
        self.assertEqual(len(result.stories[0].runs["scorer"]), 1)

    def test_unsafe_cumulative_total_is_an_explicit_calculation_failure(self):
        config = Config(clock={"initial_evidence_points": 2**53 - 1})
        client = fake_client(relevance(), make_assessment((1, 0, 0)).model_dump())
        result = evaluate(Dataset(stories=[story("overflow")]), config, client=client)
        self.assertFalse(result.complete)
        self.assertEqual(result.cumulative_points, 2**53 - 1)
        self.assertIn("calculation:", result.stories[0].error)
        self.assertIsNotNone(result.stories[0].assessment)
        self.assertIsNone(result.stories[0].calculation)
        self.assertIsNone(result.stories[0].report)

    def test_empty_dataset_never_calls_model(self):
        client = fake_client()
        result = evaluate(Dataset(stories=[]), Config(), client=client)
        self.assertTrue(result.complete)
        self.assertEqual(result.remaining_seconds, 900.0)
        self.assertEqual(result.evidence_pressure_percent, 0)
        client.responses.create.assert_not_called()


if __name__ == "__main__":
    unittest.main()
