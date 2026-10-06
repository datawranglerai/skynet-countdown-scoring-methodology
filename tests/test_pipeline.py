import unittest
from datetime import date

from skynet_countdown.config import Config
from skynet_countdown.models import Dataset, EvaluationResult, Story
from skynet_countdown.pipeline import evaluate
from skynet_countdown.scoring import remaining_seconds
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

    def test_equal_dates_preserve_input_order(self):
        dataset = Dataset(stories=[story("z"), story("a")])
        client = fake_client(relevance(False, 1), relevance(False, 1))
        result = evaluate(dataset, Config(), client=client)
        self.assertEqual([r.story.id for r in result.stories], ["z", "a"])

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
        self.assertEqual(record.report.severity_label, "NO MOVEMENT")
        self.assertEqual(record.report.clock_delta_label, "0.00 SECONDS CLOSER")
        self.assertEqual(record.report.remaining_time, "60:00")
        self.assertEqual(record.calculation.clock.delta_seconds, 0.0)

    def test_reports_disabled_still_accumulates_points_from_seed(self):
        config = Config(write_reports=False)
        config.clock.initial_evidence_points = 1000
        client = fake_client(relevance(), make_assessment((1, 1, 1)).model_dump())
        result = evaluate(Dataset(stories=[story("scored")]), config, client=client)
        self.assertEqual(result.cumulative_points, 1007)
        self.assertEqual(result.stories[0].calculation.clock.remaining_seconds_before, 1800.0)
        self.assertEqual(result.stories[0].status, "assessed")
        self.assertEqual(client.responses.create.call_count, 2)

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

    def test_empty_dataset_never_calls_model(self):
        client = fake_client()
        result = evaluate(Dataset(stories=[]), Config(), client=client)
        self.assertTrue(result.complete)
        self.assertEqual(result.remaining_seconds, 3600.0)
        client.responses.create.assert_not_called()


if __name__ == "__main__":
    unittest.main()
