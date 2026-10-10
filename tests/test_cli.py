import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openai import OpenAIError

from skynet_countdown.__main__ import main
from skynet_countdown.models import EvaluationResult
from tests.fakes import editorial, fake_client, relevance
from tests.helpers import make_assessment

ROOT = Path(__file__).resolve().parents[1]


class CLITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / "result.json"
        self.argv = [
            "--input",
            str(ROOT / "examples/stories.json"),
            "--config",
            str(ROOT / "config.toml"),
        ]

    def run_cli(self, *extra):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return main(self.argv + list(extra))

    def test_validation_needs_no_key_or_client(self):
        with patch("skynet_countdown.__main__.OpenAI") as client:
            self.assertEqual(self.run_cli("--validate-only"), 0)
            client.assert_not_called()

    def test_cli_writes_full_structured_json_using_mocked_model(self):
        client = fake_client(
            relevance(),
            make_assessment((1, 1, 1)).model_dump(),
            editorial(),
            relevance(False, 1),
        )
        with patch("skynet_countdown.__main__.OpenAI") as constructor:
            constructor.return_value.__enter__.return_value = client
            self.assertEqual(self.run_cli("--output", str(self.output)), 0)
            constructor.assert_called_once_with(timeout=180.0, max_retries=2)
        result = EvaluationResult.model_validate_json(self.output.read_text(encoding="utf-8"))
        self.assertTrue(result.complete)
        self.assertEqual(result.cumulative_points, 7)
        self.assertEqual(result.stories[0].report.story_id, "fictional-inbox-agent")
        self.assertEqual(result.stories[1].status, "excluded")

    def test_existing_output_is_not_overwritten_or_charged(self):
        self.output.write_text("existing data", encoding="utf-8")
        with patch("skynet_countdown.__main__.OpenAI") as client:
            self.assertEqual(self.run_cli("--output", str(self.output)), 1)
            client.assert_not_called()
        self.assertEqual(self.output.read_text(encoding="utf-8"), "existing data")

    def test_invalid_input_fails_before_output_or_api(self):
        bad_input = Path(self.temp.name) / "bad.json"
        bad_input.write_text(json.dumps({"stories": [{"id": "missing-fields"}]}), encoding="utf-8")
        self.argv[1] = str(bad_input)
        with patch("skynet_countdown.__main__.OpenAI") as client:
            self.assertEqual(self.run_cli("--output", str(self.output)), 1)
            client.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_input_cannot_be_used_as_output(self):
        with patch("skynet_countdown.__main__.OpenAI") as client:
            self.assertEqual(self.run_cli("--output", self.argv[1]), 1)
            client.assert_not_called()

    def test_missing_api_key_does_not_leave_empty_output(self):
        with patch("skynet_countdown.__main__.OpenAI", side_effect=OpenAIError("Missing API key")):
            self.assertEqual(self.run_cli("--output", str(self.output)), 1)
        self.assertFalse(self.output.exists())

    def test_stage_failure_saves_partial_results_and_exits_nonzero(self):
        client = fake_client(OpenAIError("Test transport failure"), relevance(False, 1))
        with patch("skynet_countdown.__main__.OpenAI") as constructor:
            constructor.return_value.__enter__.return_value = client
            self.assertEqual(self.run_cli("--output", str(self.output)), 1)
        result = EvaluationResult.model_validate_json(self.output.read_text(encoding="utf-8"))
        self.assertFalse(result.complete)
        self.assertIn("relevance:", result.stories[0].error)
        self.assertEqual(result.stories[1].status, "excluded")

    def test_missing_parent_directory_fails_before_api(self):
        with patch("skynet_countdown.__main__.OpenAI") as client:
            self.assertEqual(self.run_cli("--output", str(self.output / "nested.json")), 1)
            client.assert_not_called()

    def test_serialization_failure_removes_reserved_output_for_retry(self):
        client = fake_client(
            relevance(),
            make_assessment((1, 1, 1)).model_dump(),
            editorial(),
            relevance(False, 1),
        )
        with (
            patch("skynet_countdown.__main__.OpenAI") as constructor,
            patch.object(
                EvaluationResult, "model_dump_json", side_effect=ValueError("Cannot serialize")
            ),
        ):
            constructor.return_value.__enter__.return_value = client
            self.assertEqual(self.run_cli("--output", str(self.output)), 1)
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
