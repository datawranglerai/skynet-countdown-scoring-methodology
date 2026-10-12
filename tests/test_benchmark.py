"""Historical comparison, isolation, failure coverage and CLI tests; no API access."""

import contextlib
import copy
import io
import json
import tempfile
import unittest
from hashlib import sha256
from pathlib import Path
from typing import Any
from unittest.mock import patch

from openai import OpenAIError
from pydantic import ValidationError

from skynet_countdown.benchmark import (
    BenchmarkDataset,
    compare_assessments,
    evaluate_benchmark,
    main,
    summarize,
)
from skynet_countdown.config import Config
from tests.fakes import fake_client, make_response
from tests.helpers import make_assessment

ROOT = Path(__file__).resolve().parents[1]


def benchmark_data():
    reference = make_assessment((1, 1, 0)).model_dump()
    reference["scoring_notes"] = "HISTORICAL_REFERENCE_SECRET"
    return {
        "schema_version": "1.0",
        "name": "Small historical baseline",
        "reference_kind": "historical_model_output",
        "memory_mode": "none",
        "created_at": "2026-10-12T12:00:00Z",
        "provenance": {"export": "DATASET_PROVENANCE_SECRET"},
        "cases": [
            {
                "story": {
                    "id": "agent-access",
                    "title": "An agent receives production permissions",
                    "source_url": "https://example.com/agent-access",
                    "published_date": "2026-10-01",
                    "summary": "The agent processes external emails.",
                    "content": "The agent reads external email and accesses production records.",
                    "metadata": {"historical_score": "METADATA_LABEL_SECRET"},
                },
                "reference": reference,
                "provenance": {"export_row": "CASE_PROVENANCE_SECRET"},
                "tags": ["REFERENCE_TAG_SECRET"],
            }
        ],
    }


def dataset():
    return BenchmarkDataset.model_validate_json(json.dumps(benchmark_data()))


class BenchmarkTests(unittest.TestCase):
    def test_labels_and_metadata_never_reach_model_and_retrieval_is_forced_off(self):
        client = fake_client(make_assessment((1, 1, 0)).model_dump())
        config = Config.model_validate(
            {"scorer": {"web_search": True}, "clock": {"initial_evidence_points": 100}}
        )
        result = evaluate_benchmark(dataset(), config, client=client)
        client.responses.create.assert_called_once()
        request = client.responses.create.call_args.kwargs
        payload = json.loads(request["input"][0]["content"])
        self.assertEqual(set(payload), {"story"})
        self.assertEqual(payload["story"]["content"], dataset().cases[0].story.content)
        self.assertNotIn("metadata", payload["story"])
        for marker in (
            "HISTORICAL_REFERENCE_SECRET",
            "DATASET_PROVENANCE_SECRET",
            "METADATA_LABEL_SECRET",
            "CASE_PROVENANCE_SECRET",
            "REFERENCE_TAG_SECRET",
        ):
            self.assertNotIn(marker, json.dumps(request))
        self.assertEqual(request["text"]["format"]["name"], "Assessment")
        self.assertNotIn("tools", request)
        self.assertNotIn("previous_response_id", request)
        self.assertIn("No retrieval tools are available", request["instructions"])
        self.assertFalse(request["store"])
        self.assertFalse(result["config"]["write_reports"])
        self.assertFalse(result["config"]["scorer"]["web_search"])
        self.assertEqual(result["config"]["clock"]["initial_evidence_points"], 0)
        self.assertTrue(config.scorer.web_search)
        self.assertTrue(config.write_reports)
        self.assertEqual(config.clock.initial_evidence_points, 100)

    def test_weighted_total_is_distinct_from_raw_total_and_flags_are_compared(self):
        candidate = make_assessment((1, 1, 1))
        candidate.is_leading_indicator = True
        candidate.leading_indicator_note = "A deployment constraint was removed."
        result = compare_assessments(make_assessment((1, 1, 0)), candidate, Config())
        self.assertEqual(result["reference_calculation"]["total_score"], 3)
        self.assertEqual(result["actual_calculation"]["total_score"], 7)
        self.assertEqual(result["reference_calculation"]["raw_source_total"], 2)
        self.assertEqual(result["actual_calculation"]["raw_source_total"], 3)
        self.assertEqual(result["signed_total_error"], 4)
        self.assertEqual(result["absolute_total_error"], 4)
        self.assertEqual(
            result["components"]["trifecta.t3"], {"expected": 0, "actual": 1, "delta": 1}
        )
        self.assertTrue(result["severity_changed"])
        self.assertTrue(result["full_trifecta_changed"])
        self.assertTrue(result["leading_indicator_changed"])
        self.assertEqual(result["actual_calculation"]["clock"]["cumulative_points_before"], 0)

    def test_same_total_can_hide_component_differences(self):
        result = compare_assessments(
            make_assessment((1, 1, 0)), make_assessment((1, 0, 1)), Config()
        )
        self.assertEqual(result["signed_total_error"], 0)
        self.assertFalse(result["all_components_agree"])
        self.assertEqual(result["components"]["trifecta.t2"]["delta"], -1)
        self.assertEqual(result["components"]["trifecta.t3"]["delta"], 1)

    def test_repetitions_are_independent_and_component_variation_is_reported(self):
        client = fake_client(
            make_assessment((1, 1, 0)).model_dump(), make_assessment((1, 0, 1)).model_dump()
        )
        result = evaluate_benchmark(dataset(), Config(), client=client, repetitions=2)
        self.assertTrue(result["complete"])
        requests = [call.kwargs for call in client.responses.create.call_args_list]
        self.assertEqual(len(requests), 2)
        for request in requests:
            self.assertEqual(len(request["input"]), 1)
            self.assertEqual(request["input"][0]["role"], "user")
            self.assertNotIn("previous_response_id", request)
            self.assertNotIn("conversation", request)
        summary = result["summary"]
        self.assertEqual(summary["repetition_consistency"]["inconsistent_case_rate"], 1)
        self.assertEqual(
            summary["repetition_consistency"]["inconsistent_story_ids"], ["agent-access"]
        )
        conditional = summary["conditional_on_successful_assessments"]
        self.assertEqual(conditional["all_components_agreement_rate"], 0.5)
        self.assertEqual(conditional["mean_absolute_total_error"], 0)
        self.assertEqual(summary["recorded_total_tokens"], 60)

    def test_failure_preserves_audit_and_does_not_hide_later_repetitions_or_cases(self):
        values = benchmark_data()
        values["cases"].append(copy.deepcopy(values["cases"][0]))
        values["cases"][1]["story"]["id"] = "second-case"
        inputs = BenchmarkDataset.model_validate_json(json.dumps(values))
        client = fake_client(
            make_response(
                "{}", status="incomplete", incomplete_details={"reason": "max_output_tokens"}
            ),
            make_assessment((1, 1, 0)).model_dump(),
            OpenAIError("Test transport failure"),
            make_assessment((1, 1, 1)).model_dump(),
        )
        result = evaluate_benchmark(inputs, Config(), client=client, repetitions=2)
        self.assertFalse(result["complete"])
        self.assertEqual(client.responses.create.call_count, 4)
        summary = result["summary"]
        self.assertEqual(summary["expected_assessments"], 4)
        self.assertEqual(summary["successful_assessments"], 2)
        self.assertEqual(summary["failed_assessments"], 2)
        self.assertEqual(summary["missing_assessments"], 0)
        self.assertEqual(summary["successful_assessment_coverage"], 0.5)
        conditional = summary["conditional_on_successful_assessments"]
        self.assertEqual(conditional["denominator"], 2)
        self.assertEqual(conditional["mean_signed_total_error"], 2)
        consistency = summary["repetition_consistency"]
        self.assertEqual(consistency["eligible_cases_with_multiple_repetitions"], 0)
        self.assertEqual(consistency["cases_with_failed_or_missing_assessments"], 2)
        self.assertIsNone(consistency["inconsistent_case_rate"])
        attempt = result["cases"][0]["attempts"][0]
        self.assertIsNone(attempt["assessment"])
        self.assertIsNone(attempt["comparison"])
        self.assertEqual(attempt["audit"][0]["status"], "incomplete")
        self.assertIn("ChainError", attempt["error"])

    def test_all_failed_and_missing_assessments_have_no_agreement_denominator(self):
        result = evaluate_benchmark(dataset(), Config(), client=fake_client(OpenAIError("Failure")))
        summary = result["summary"]
        self.assertEqual(summary["conditional_on_successful_assessments"]["denominator"], 0)
        self.assertIsNone(
            summary["conditional_on_successful_assessments"]["mean_absolute_total_error"]
        )
        result["cases"][0]["attempts"].clear()
        missing = summarize(result["cases"], 1)
        self.assertEqual(missing["failed_assessments"], 0)
        self.assertEqual(missing["missing_assessments"], 1)

    def test_correction_history_stays_with_its_own_repetition(self):
        client = fake_client(
            "invalid JSON", make_assessment().model_dump(), make_assessment().model_dump()
        )
        result = evaluate_benchmark(dataset(), Config(), client=client, repetitions=2)
        self.assertTrue(result["complete"])
        self.assertEqual(result["summary"]["structured_output_corrections"], 1)
        self.assertEqual(len(client.responses.create.call_args_list[-1].kwargs["input"]), 1)
        self.assertEqual(len(result["cases"][0]["attempts"][0]["audit"]), 2)

    def test_reproducibility_metadata_and_audit_are_recorded(self):
        response = make_response(
            make_assessment().model_dump(), model="model-snapshot", id="resp_benchmark"
        )
        result = evaluate_benchmark(dataset(), Config(), client=fake_client(response))
        prompt = (ROOT / "skynet_countdown/prompts/scorer.txt").read_text(encoding="utf-8")
        self.assertEqual(result["prompt_sha256"]["scorer"], sha256(prompt.encode()).hexdigest())
        self.assertEqual(
            result["code_sha256"]["llm.py"],
            sha256((ROOT / "skynet_countdown/llm.py").read_bytes()).hexdigest(),
        )
        self.assertEqual(
            result["dataset_sha256"], sha256(dataset().model_dump_json().encode()).hexdigest()
        )
        self.assertEqual(result["reference_kind"], "historical_model_output")
        self.assertEqual(result["memory_mode"], "none")
        self.assertGreaterEqual(result["elapsed_seconds"], 0)
        attempt = result["cases"][0]["attempts"][0]
        self.assertGreaterEqual(attempt["elapsed_seconds"], 0)
        self.assertEqual(attempt["audit"][0]["response_id"], "resp_benchmark")
        self.assertEqual(result["summary"]["returned_models"], ["model-snapshot"])

    def test_invalid_dataset_content_references_duplicate_ids_and_modes_are_rejected(self):
        changes = [
            lambda data: data.update(cases=[]),
            lambda data: data.update(memory_mode="postgres"),
            lambda data: data.update(reference_kind="gold"),
            lambda data: data["cases"].append(copy.deepcopy(data["cases"][0])),
            lambda data: data["cases"][0]["story"].update(content=None),
            lambda data: data["cases"][0]["story"].update(content="  "),
            lambda data: data["cases"][0].update(reference=None),
            lambda data: data["cases"][0]["reference"]["trifecta"]["t1"].update(score=2),
        ]
        for change in changes:
            with self.subTest(change=change):
                data = benchmark_data()
                change(data)
                with self.assertRaises(ValidationError):
                    BenchmarkDataset.model_validate_json(json.dumps(data))

    def test_invalid_repetitions_and_mutated_config_fail_before_model_calls(self):
        client = fake_client()
        # Include invalid runtime types deliberately, beyond the function's typed contract.
        invalid_repetitions: tuple[Any, ...] = (0, -1, True, 1.5)
        for repetitions in invalid_repetitions:
            with self.subTest(repetitions=repetitions), self.assertRaises(ValueError):
                evaluate_benchmark(dataset(), Config(), client=client, repetitions=repetitions)
        config = Config()
        config.scorer.model = "  "
        with self.assertRaises(ValidationError):
            evaluate_benchmark(dataset(), config, client=client)
        client.responses.create.assert_not_called()

    def test_prior_run_comparison_reports_shifted_means_and_failed_coverage(self):
        values = benchmark_data()
        values["cases"].append(copy.deepcopy(values["cases"][0]))
        values["cases"][1]["story"]["id"] = "second-case"
        inputs = BenchmarkDataset.model_validate_json(json.dumps(values))
        baseline = evaluate_benchmark(
            inputs,
            Config.model_validate({"scorer": {"model": "incumbent"}}),
            client=fake_client(
                make_assessment((1, 1, 0)).model_dump(),
                make_assessment((1, 1, 1)).model_dump(),
                OpenAIError("First-case failure"),
                OpenAIError("No second-case assessment"),
                OpenAIError("No second-case assessment"),
                OpenAIError("No second-case assessment"),
            ),
            repetitions=3,
        )
        result = evaluate_benchmark(
            inputs,
            Config.model_validate(
                {
                    "scorer": {"model": "candidate"},
                    "relevance": {"model": "inactive-relevance"},
                    "writer": {"model": "inactive-writer"},
                    "minimum_relevance_score": 9,
                }
            ),
            client=fake_client(
                make_assessment((1, 1, 1)).model_dump(),
                make_assessment((1, 1, 1)).model_dump(),
                make_assessment((1, 1, 0)).model_dump(),
                OpenAIError("Candidate second-case failure"),
            ),
            repetitions=2,
            baseline=baseline,
        )
        comparison = result["current_vs_baseline"]
        self.assertEqual(comparison["total_cases"], 2)
        self.assertEqual(comparison["paired_successful_cases"], 1)
        self.assertEqual(comparison["unpaired_or_unusable_cases"], 1)
        self.assertEqual(comparison["mean_weighted_score_delta_over_paired_cases"], 2)
        self.assertEqual(comparison["coverage"]["baseline"]["expected_assessments"], 6)
        self.assertEqual(comparison["coverage"]["baseline"]["successful_assessments"], 2)
        self.assertEqual(comparison["coverage"]["current"]["expected_assessments"], 4)
        self.assertEqual(comparison["coverage"]["current"]["successful_assessments"], 3)
        first, second = comparison["cases"]
        self.assertEqual(first["component_mean_deltas"]["trifecta.t3"], 0.5)
        self.assertEqual(first["baseline"]["mean_weighted_score"], 5)
        self.assertEqual(first["current"]["mean_weighted_score"], 7)
        self.assertEqual(first["baseline"]["expected_assessments"], 3)
        self.assertEqual(first["baseline"]["successful_assessments"], 2)
        self.assertEqual(first["baseline"]["failed_assessments"], 1)
        self.assertEqual(first["current"]["expected_assessments"], 2)
        self.assertEqual(second["baseline"]["successful_assessments"], 0)
        self.assertEqual(second["baseline"]["failed_assessments"], 3)
        self.assertEqual(second["current"]["successful_assessments"], 1)
        self.assertIsNone(second["component_mean_deltas"])
        self.assertIsNone(second["weighted_score_mean_delta"])

    def test_prior_run_missing_case_and_attempt_are_retained(self):
        baseline = evaluate_benchmark(
            dataset(), Config(), client=fake_client(make_assessment().model_dump())
        )
        for remove_case in (True, False):
            previous = copy.deepcopy(baseline)
            if remove_case:
                previous["cases"].clear()
            else:
                previous["cases"][0]["attempts"].clear()
            result = evaluate_benchmark(
                dataset(),
                Config(),
                client=fake_client(make_assessment().model_dump()),
                baseline=previous,
            )
            comparison = result["current_vs_baseline"]
            self.assertEqual(comparison["paired_successful_cases"], 0)
            self.assertEqual(comparison["unpaired_or_unusable_cases"], 1)
            self.assertIsNone(comparison["mean_weighted_score_delta_over_paired_cases"])
            self.assertEqual(comparison["coverage"]["baseline"]["missing_assessments"], 1)
            case = comparison["cases"][0]
            if remove_case:
                self.assertIsNone(case["baseline"])
            else:
                self.assertEqual(case["baseline"]["missing_assessments"], 1)

    def test_direct_prior_comparison_rejects_mismatch_before_calls(self):
        baseline = evaluate_benchmark(
            dataset(), Config(), client=fake_client(make_assessment().model_dump())
        )
        baseline["prompt_sha256"]["scorer"] = "wrong"
        client = fake_client()
        with self.assertRaisesRegex(ValueError, "prompt"):
            evaluate_benchmark(dataset(), Config(), client=client, baseline=baseline)
        client.responses.create.assert_not_called()


class BenchmarkCLITests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.input = Path(temporary.name) / "benchmark.json"
        self.output = Path(temporary.name) / "report.json"
        self.config = Path(temporary.name) / "config.toml"
        # Isolate CLI contracts from model choices in the user's working configuration.
        self.config.write_text("", encoding="utf-8")
        self.input.write_text(json.dumps(benchmark_data()), encoding="utf-8")
        self.argv = ["--dataset", str(self.input), "--config", str(self.config)]

    def invoke(self, *extra):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return main(self.argv + list(extra))

    def test_validate_only_does_not_create_a_client_or_output(self):
        with patch("skynet_countdown.benchmark.OpenAI") as constructor:
            self.assertEqual(self.invoke("--validate-only", "--output", str(self.output)), 0)
            constructor.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_disagreement_is_saved_without_nonzero_exit_and_model_can_be_overridden(self):
        client = fake_client(make_assessment((1, 1, 1)).model_dump())
        with patch("skynet_countdown.benchmark.OpenAI") as constructor:
            constructor.return_value.__enter__.return_value = client
            self.assertEqual(
                self.invoke("--output", str(self.output), "--model", "candidate-model"), 0
            )
            constructor.assert_called_once_with(timeout=180.0, max_retries=2)
        result = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertTrue(result["complete"])
        self.assertEqual(result["dataset_sha256"], sha256(self.input.read_bytes()).hexdigest())
        self.assertEqual(result["dataset_sha256_basis"], "file_bytes")
        self.assertEqual(client.responses.create.call_args.kwargs["model"], "candidate-model")
        self.assertEqual(
            result["summary"]["conditional_on_successful_assessments"]["mean_signed_total_error"], 4
        )

    def test_failed_assessment_is_saved_and_exits_nonzero(self):
        with patch("skynet_countdown.benchmark.OpenAI") as constructor:
            constructor.return_value.__enter__.return_value = fake_client(OpenAIError("Failure"))
            self.assertEqual(self.invoke("--output", str(self.output)), 1)
        result = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertFalse(result["complete"])
        self.assertEqual(result["summary"]["failed_assessments"], 1)

    def test_existing_output_and_dataset_cannot_be_overwritten(self):
        self.output.write_text("Existing result", encoding="utf-8")
        for path in (self.output, self.input):
            before = path.read_bytes()
            with patch("skynet_countdown.benchmark.OpenAI") as constructor:
                self.assertEqual(self.invoke("--output", str(path)), 1)
                constructor.assert_not_called()
            self.assertEqual(path.read_bytes(), before)

    def test_invalid_inputs_and_missing_output_parent_fail_before_api(self):
        for options in (
            ("--repetitions", "0"),
            ("--model", "   "),
            ("--config", str(self.input)),
            ("--output", str(self.output / "missing.json")),
        ):
            with (
                self.subTest(options=options),
                patch("skynet_countdown.benchmark.OpenAI") as constructor,
            ):
                self.assertEqual(self.invoke("--output", str(self.output), *options), 1)
                constructor.assert_not_called()
                self.assertFalse(self.output.exists())
        self.input.write_text("{}", encoding="utf-8")
        with patch("skynet_countdown.benchmark.OpenAI") as constructor:
            self.assertEqual(self.invoke("--output", str(self.output)), 1)
            constructor.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_output_is_reserved_before_client_creation_and_removed_on_client_failure(self):
        def unavailable(**kwargs):
            self.assertTrue(self.output.exists())
            raise OpenAIError("Missing API key")

        with patch("skynet_countdown.benchmark.OpenAI", side_effect=unavailable):
            self.assertEqual(self.invoke("--output", str(self.output)), 1)
        self.assertFalse(self.output.exists())

    def test_serialization_error_removes_only_reserved_output(self):
        before = self.input.read_bytes()
        with (
            patch("skynet_countdown.benchmark.OpenAI") as constructor,
            patch(
                "skynet_countdown.benchmark.json.dump", side_effect=ValueError("Cannot serialize")
            ),
        ):
            constructor.return_value.__enter__.return_value = fake_client(
                make_assessment().model_dump()
            )
            self.assertEqual(self.invoke("--output", str(self.output)), 1)
        self.assertFalse(self.output.exists())
        self.assertEqual(self.input.read_bytes(), before)

    def test_prior_run_cli_rejects_incomparable_or_invalid_reports_before_client_creation(self):
        baseline = evaluate_benchmark(
            dataset(),
            Config(),
            client=fake_client(make_assessment().model_dump()),
            dataset_sha256=sha256(self.input.read_bytes()).hexdigest(),
        )
        path = self.output.parent / "baseline.json"
        changes = [
            lambda data: data.update(dataset_sha256="wrong"),
            lambda data: data.update(dataset_sha256_basis="model_dump_json"),
            lambda data: data["prompt_sha256"].update(scorer="wrong"),
            lambda data: data["code_sha256"].update({"llm.py": "wrong"}),
            lambda data: data["config"]["scorer"].update(reasoning_effort="low"),
            lambda data: data["config"]["scoring"].update(trifecta_points=[0, 1, 3, 8]),
            lambda data: data.update(memory_mode="postgres"),
            lambda data: data.update(schema_version="2.0"),
            lambda data: data.update(repetitions=0),
            lambda data: data["cases"][0]["story"].update(id="unknown-story"),
            lambda data: data["cases"][0]["attempts"][0].update(repetition=2),
            lambda data: data["cases"][0]["attempts"][0].update(assessment={}),
        ]
        for change in changes:
            data = copy.deepcopy(baseline)
            change(data)
            path.write_text(json.dumps(data), encoding="utf-8")
            with (
                self.subTest(change=change),
                patch("skynet_countdown.benchmark.OpenAI") as constructor,
            ):
                self.assertEqual(
                    self.invoke("--output", str(self.output), "--baseline", str(path)), 1
                )
                constructor.assert_not_called()
                self.assertFalse(self.output.exists())
        for malformed in ("null", "[]", "{}", "invalid JSON"):
            path.write_text(malformed, encoding="utf-8")
            with patch("skynet_countdown.benchmark.OpenAI") as constructor:
                self.assertEqual(
                    self.invoke("--output", str(self.output), "--baseline", str(path)), 1
                )
                constructor.assert_not_called()

    def test_prior_run_cli_compares_compatible_reports(self):
        baseline = evaluate_benchmark(
            dataset(),
            Config(),
            client=fake_client(make_assessment((1, 1, 0)).model_dump()),
            dataset_sha256=sha256(self.input.read_bytes()).hexdigest(),
        )
        path = self.output.parent / "baseline.json"
        path.write_text(json.dumps(baseline), encoding="utf-8")
        with patch("skynet_countdown.benchmark.OpenAI") as constructor:
            self.assertEqual(self.invoke("--validate-only", "--baseline", str(path)), 0)
            constructor.assert_not_called()
            constructor.return_value.__enter__.return_value = fake_client(
                make_assessment((1, 1, 1)).model_dump()
            )
            self.assertEqual(self.invoke("--output", str(self.output), "--baseline", str(path)), 0)
        report = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertEqual(
            report["current_vs_baseline"]["mean_weighted_score_delta_over_paired_cases"], 4
        )


if __name__ == "__main__":
    unittest.main()
