"""Input, configuration, and model judgments stay strict at their boundaries."""

import json
import tempfile
import unittest
from pathlib import Path

from fakes import editorial, relevance
from helpers import make_assessment
from pydantic import ValidationError

from skynet_countdown.config import (
    Config,
    ScoringConfig,
    SeverityThresholds,
    load_config,
)
from skynet_countdown.models import Assessment, Dataset, Editorial, Relevance


def supplied_story(**overrides):
    return {
        "id": "story-1",
        "title": "A documented deployment",
        "source_url": "https://example.org/story",
        "published_date": "2026-10-06",
        "summary": "An agent reads incoming messages and updates a private system.",
        **overrides,
    }


class ModelContractTests(unittest.TestCase):
    def test_every_object_in_each_llm_schema_is_closed_and_fully_required(self):
        def objects(value):
            if isinstance(value, dict):
                if value.get("type") == "object":
                    yield value
                for child in value.values():
                    yield from objects(child)
            elif isinstance(value, list):
                for child in value:
                    yield from objects(child)

        for output_type in (Relevance, Assessment, Editorial):
            for schema in objects(output_type.model_json_schema()):
                with self.subTest(model=output_type.__name__, object=schema.get("title")):
                    self.assertIs(schema.get("additionalProperties"), False)
                    self.assertEqual(set(schema.get("required", [])), set(schema["properties"]))

    def test_scorer_cannot_return_totals_classification_clock_or_cve_fields(self):
        for field, value in (
            ("total_score", 17),
            ("trifecta_points", 7),
            ("amplifier_points", 10),
            ("classification", "EXISTENTIAL"),
            ("seconds_moved", 42),
            ("clock", {}),
            ("cve", "CVE-2026-1234"),
            ("cve_analysis", "Unrequested enrichment"),
        ):
            with self.subTest(field=field):
                assessment = make_assessment().model_dump()
                assessment[field] = value
                with self.assertRaises(ValidationError) as raised:
                    Assessment.model_validate_json(json.dumps(assessment))
                self.assertTrue(
                    any(
                        error["loc"] == (field,) and error["type"] == "extra_forbidden"
                        for error in raised.exception.errors()
                    )
                )

    def test_all_eight_criteria_reject_coercions_and_out_of_range_values(self):
        valid = make_assessment().model_dump()
        for group, upper_bound in (("trifecta", 1), ("amplifiers", 2)):
            for criterion in valid[group]:
                for invalid in (True, False, 0.0, 1.0, "1", -1, upper_bound + 1):
                    with self.subTest(group=group, criterion=criterion, score=invalid):
                        assessment = make_assessment().model_dump()
                        assessment[group][criterion]["score"] = invalid
                        with self.assertRaises(ValidationError):
                            Assessment.model_validate_json(json.dumps(assessment))

    def test_criterion_explanations_are_required_and_not_blank(self):
        for invalid in (None, "", "   "):
            with self.subTest(rationale=invalid):
                assessment = make_assessment().model_dump()
                assessment["trifecta"]["t1"]["rationale"] = invalid
                with self.assertRaises(ValidationError):
                    Assessment.model_validate_json(json.dumps(assessment))
        assessment = make_assessment().model_dump()
        del assessment["amplifiers"]["physical_weaponisation"]["rationale"]
        with self.assertRaises(ValidationError):
            Assessment.model_validate_json(json.dumps(assessment))

    def test_leading_indicator_flag_and_explanation_must_agree(self):
        for flag, note in ((True, ""), (True, "   "), (False, "An early signal")):
            with self.subTest(flag=flag, note=note):
                assessment = make_assessment().model_dump()
                assessment.update(is_leading_indicator=flag, leading_indicator_note=note)
                with self.assertRaises(ValidationError):
                    Assessment.model_validate_json(json.dumps(assessment))
        assessment = make_assessment().model_dump()
        assessment.update(is_leading_indicator=True, leading_indicator_note="An early signal")
        self.assertTrue(Assessment.model_validate_json(json.dumps(assessment)).is_leading_indicator)

    def test_relevance_is_a_strict_bounded_judgment(self):
        for invalid in (True, 1.0, "8", 0, 11):
            with self.subTest(score=invalid), self.assertRaises(ValidationError):
                Relevance.model_validate_json(json.dumps(relevance(score=invalid)))
        for update in (
            {"relevant_to_skynet": "true"},
            {"primary_dimension": "other"},
            {"relevance_rationale": "   "},
        ):
            with self.subTest(update=update), self.assertRaises(ValidationError):
                Relevance.model_validate_json(json.dumps({**relevance(), **update}))

    def test_writer_keeps_prose_fields_and_limits_headline_length(self):
        result = Editorial.model_validate_json(json.dumps(editorial()))
        self.assertEqual(result.the_story, editorial()["the_story"])
        self.assertEqual(result.our_take, editorial()["our_take"])
        for update in (
            {"headline": "word " * 13},
            {"the_story": " "},
            {"our_take": ""},
            {"severity_label": "CRITICAL"},
            {"clock_delta_label": "42 seconds"},
        ):
            with self.subTest(update=update), self.assertRaises(ValidationError):
                Editorial.model_validate_json(json.dumps({**editorial(), **update}))

    def test_input_accepts_supplied_metadata_without_requiring_scraping_fields(self):
        value = supplied_story(metadata={"publisher": "Example", "external_id": 12})
        dataset = Dataset.model_validate_json(json.dumps({"stories": [value]}))
        story = dataset.stories[0]
        self.assertEqual(story.id, "story-1")
        self.assertIsNone(story.content)
        self.assertIsNone(story.reddit_post_url)
        self.assertEqual(story.metadata, value["metadata"])
        self.assertEqual(story.published_date.isoformat(), "2026-10-06")

    def test_input_rejects_duplicate_ids_including_after_whitespace_normalization(self):
        for second_id in ("story-1", " story-1 "):
            with (
                self.subTest(second_id=second_id),
                self.assertRaisesRegex(ValidationError, "IDs must be unique"),
            ):
                Dataset.model_validate_json(
                    json.dumps(
                        {
                            "stories": [supplied_story(), supplied_story(id=second_id)],
                        }
                    )
                )

    def test_input_rejects_malformed_stories_and_precomputed_scores(self):
        for update in (
            {"id": "  "},
            {"title": ""},
            {"summary": "  "},
            {"source_url": "not a URL"},
            {"source_url": "file:///private/story"},
            {"published_date": "2026-02-30"},
            {"published_date": "06/10/2026"},
            {"total_score": 17},
            {"relevance_score": 8},
            {"content": "  "},
        ):
            with self.subTest(update=update), self.assertRaises(ValidationError):
                Dataset.model_validate_json(json.dumps({"stories": [supplied_story(**update)]}))
        value = supplied_story()
        del value["summary"]
        with self.assertRaises(ValidationError):
            Dataset.model_validate_json(json.dumps({"stories": [value]}))


class ConfigContractTests(unittest.TestCase):
    def test_toml_loads_custom_chain_scoring_and_clock_settings(self):
        content = """
minimum_relevance_score = 4
write_reports = false
request_timeout_seconds = 25.0
api_max_retries = 0
[scorer]
model = "custom-model"
reasoning_effort = "omit"
max_iterations = 4
web_search = true
web_search_context_size = "low"
max_tool_calls = 2
[scoring]
trifecta_points = [0, 2, 4, 8]
[scoring.severity_thresholds]
NOTABLE = 4
SIGNIFICANT = 6
CRITICAL = 8
EXISTENTIAL = 15
[clock]
initial_seconds = 7200.0
half_scale_points = 500.0
initial_evidence_points = 113
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.toml"
            path.write_text(content, encoding="utf-8")
            config = load_config(path)
        self.assertEqual(config.minimum_relevance_score, 4)
        self.assertFalse(config.write_reports)
        self.assertEqual(config.request_timeout_seconds, 25)
        self.assertEqual(config.api_max_retries, 0)
        self.assertEqual(config.scorer.model, "custom-model")
        self.assertEqual(config.scorer.max_iterations, 4)
        self.assertTrue(config.scorer.web_search)
        self.assertEqual(config.scorer.web_search_context_size, "low")
        self.assertEqual(config.scorer.max_tool_calls, 2)
        self.assertEqual(config.scoring.trifecta_points, [0, 2, 4, 8])
        self.assertEqual(config.scoring.severity_thresholds.CANARY, 1)
        self.assertEqual(config.scoring.severity_thresholds.EXISTENTIAL, 15)
        self.assertEqual(config.clock.initial_seconds, 7200)
        self.assertEqual(config.clock.half_scale_points, 500)
        self.assertEqual(config.clock.initial_evidence_points, 113)

    def test_toml_typos_fail_instead_of_silently_using_defaults(self):
        for content in (
            "minimum_relavance_score = 4",
            "[relevance]\nmax_iteration = 4",
            "[scorer]\nweb_serach = true",
            "[clock]\nhalf_scale_point = 500.0",
        ):
            with self.subTest(content=content), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "settings.toml"
                path.write_text(content, encoding="utf-8")
                with self.assertRaises(ValidationError) as raised:
                    load_config(path)
                self.assertTrue(
                    any(error["type"] == "extra_forbidden" for error in raised.exception.errors())
                )

    def test_chain_attempt_token_and_tool_limits_must_be_positive_integers(self):
        for chain in ("relevance", "scorer", "writer"):
            for field in ("max_iterations", "max_output_tokens"):
                for value in (0, -1, True, 1.0, "2"):
                    with (
                        self.subTest(chain=chain, field=field, value=value),
                        self.assertRaises(ValidationError),
                    ):
                        Config.model_validate({chain: {field: value}})
        for value in (0, -1, False, 1.0):
            with self.subTest(max_tool_calls=value), self.assertRaises(ValidationError):
                Config.model_validate({"scorer": {"max_tool_calls": value}})

    def test_timeouts_and_clock_constants_are_positive_and_finite(self):
        for value in (0, -1, float("inf"), float("nan"), True, "30"):
            for field in ("request_timeout_seconds", "initial_seconds", "half_scale_points"):
                with self.subTest(field=field, value=value):
                    config = (
                        {field: value}
                        if field == "request_timeout_seconds"
                        else {
                            "clock": {field: value},
                        }
                    )
                    with self.assertRaises(ValidationError):
                        Config.model_validate(config)

    def test_thresholds_start_at_one_and_are_strictly_increasing(self):
        for values in (
            {"CANARY": 0},
            {"CANARY": 2},
            {"NOTABLE": 1},
            {"SIGNIFICANT": 3},
            {"CRITICAL": 4},
            {"EXISTENTIAL": 7},
        ):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                SeverityThresholds.model_validate(values)

    def test_trifecta_lookup_has_four_nondecreasing_integer_entries_starting_at_zero(self):
        for points in (
            [0, 1, 3],
            [0, 1, 3, 7, 9],
            [1, 2, 3, 7],
            [0, 3, 1, 7],
            [0, 1, 3, -1],
            [0, 1, 3, 7.0],
            [0, True, 3, 7],
        ):
            with self.subTest(points=points), self.assertRaises(ValidationError):
                ScoringConfig(trifecta_points=points)

    def test_other_invalid_config_is_not_coerced_or_ignored(self):
        for config in (
            {"minimum_relevance_score": 0},
            {"minimum_relevance_score": 11},
            {"minimum_report_score": -1},
            {"api_max_retries": -1},
            {"api_max_retries": True},
            {"clock": {"initial_evidence_points": -1}},
            {"relevance": {"model": " "}},
            {"writer": {"reasoning_effort": "ultra"}},
            {"scorer": {"web_search": "false"}},
            {"scorer": {"web_search_context_size": "huge"}},
            {"writer": {"web_search": True}},
        ):
            with self.subTest(config=config), self.assertRaises(ValidationError):
                Config.model_validate(config)


if __name__ == "__main__":
    unittest.main()
