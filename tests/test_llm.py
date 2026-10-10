"""Exercise the structured-output boundary without making API requests."""

import copy
import json
import unittest

from fakes import editorial, fake_client, make_response, relevance
from helpers import make_assessment

from skynet_countdown.config import ChainConfig, ScorerConfig
from skynet_countdown.llm import ChainError, run_chain
from skynet_countdown.models import Assessment, Editorial, Relevance


class ChainTests(unittest.TestCase):
    def invoke(self, client, *, output_type=Relevance, settings=None, audit=None):
        return run_chain(
            client,
            instructions="Evaluate only the supplied story.",
            payload={"title": "An agent's permissions", "content": 'Evidence: "caf\u00e9".'},
            output_type=output_type,
            settings=settings if settings is not None else ChainConfig(),
            audit=audit if audit is not None else [],
        )

    def test_custom_settings_and_structured_output_are_forwarded(self):
        client = fake_client(relevance())
        settings = ChainConfig(
            model="chosen-model",
            reasoning_effort="low",
            max_output_tokens=1234,
        )
        result = self.invoke(client, settings=settings)

        self.assertIsInstance(result, Relevance)
        self.assertEqual(result.relevance_score, 8)
        client.responses.create.assert_called_once()
        request = client.responses.create.call_args.kwargs
        self.assertEqual(request["model"], "chosen-model")
        self.assertEqual(request["reasoning"], {"effort": "low"})
        self.assertEqual(request["max_output_tokens"], 1234)
        self.assertIs(request["store"], False)
        self.assertIn("Evaluate only the supplied story.", request["instructions"])
        self.assertEqual(
            json.loads(request["input"][0]["content"]),
            {
                "title": "An agent's permissions",
                "content": 'Evidence: "caf\u00e9".',
            },
        )
        response_format = request["text"]["format"]
        self.assertEqual(response_format["type"], "json_schema")
        self.assertEqual(response_format["name"], "Relevance")
        self.assertIs(response_format["strict"], True)
        self.assertIn("relevance_score", response_format["schema"]["required"])

    def test_relevance_and_writer_requests_have_no_retrieval_tools(self):
        for output_type, value in ((Relevance, relevance()), (Editorial, editorial())):
            with self.subTest(output_type=output_type.__name__):
                client = fake_client(value)
                self.invoke(client, output_type=output_type)
                request = client.responses.create.call_args.kwargs
                for option in ("tools", "max_tool_calls", "include"):
                    self.assertNotIn(option, request)

    def test_reasoning_can_be_omitted_for_models_without_the_option(self):
        client = fake_client(relevance())
        self.invoke(client, settings=ChainConfig(reasoning_effort="omit"))
        self.assertNotIn("reasoning", client.responses.create.call_args.kwargs)

    def test_scorer_search_is_opt_in_and_forwards_context_cap_and_sources(self):
        for enabled in (False, True):
            with self.subTest(web_search=enabled):
                client = fake_client(make_assessment().model_dump())
                self.invoke(
                    client,
                    output_type=Assessment,
                    settings=ScorerConfig(
                        web_search=enabled,
                        web_search_context_size="high",
                        max_tool_calls=3,
                    ),
                )
                request = client.responses.create.call_args.kwargs
                if enabled:
                    self.assertEqual(
                        request["tools"],
                        [
                            {
                                "type": "web_search",
                                "search_context_size": "high",
                            }
                        ],
                    )
                    self.assertEqual(request["max_tool_calls"], 3)
                    self.assertEqual(request["include"], ["web_search_call.action.sources"])
                else:
                    for option in ("tools", "max_tool_calls", "include"):
                        self.assertNotIn(option, request)

    def test_schema_correction_retries_with_feedback_and_audits_each_response(self):
        invalid = relevance(score=11)
        responses = iter(
            (
                make_response(invalid, id="resp_invalid", model="first-model"),
                make_response(relevance(), id="resp_corrected", model="second-model"),
            )
        )
        requests = []
        client = fake_client()

        def respond(**kwargs):
            requests.append(copy.deepcopy(kwargs))
            return next(responses)

        client.responses.create.side_effect = respond
        audit = []
        result = self.invoke(client, settings=ChainConfig(max_iterations=2), audit=audit)

        self.assertEqual(result.relevance_score, 8)
        self.assertEqual(len(requests), 2)
        self.assertEqual(len(requests[0]["input"]), 1)
        correction = requests[1]["input"]
        self.assertEqual(
            [message["role"] for message in correction],
            [
                "user",
                "assistant",
                "user",
            ],
        )
        self.assertEqual(json.loads(correction[1]["content"]), invalid)
        self.assertIn("relevance_score", correction[2]["content"])
        self.assertIn("less_than_equal", correction[2]["content"])
        self.assertEqual([run.response_id for run in audit], ["resp_invalid", "resp_corrected"])
        self.assertEqual([run.model for run in audit], ["first-model", "second-model"])
        self.assertTrue(all(run.status == "completed" for run in audit))
        self.assertTrue(all(run.usage["total_tokens"] == 30 for run in audit))

    def test_invalid_outputs_exhaust_exactly_the_configured_attempts(self):
        for attempts in (1, 3):
            with self.subTest(max_iterations=attempts):
                client = fake_client(*("not JSON" for _ in range(attempts)))
                audit = []
                with self.assertRaisesRegex(ChainError, f"after {attempts} attempt"):
                    self.invoke(client, settings=ChainConfig(max_iterations=attempts), audit=audit)
                self.assertEqual(client.responses.create.call_count, attempts)
                self.assertEqual(len(audit), attempts)

    def test_invalid_writer_metadata_is_corrected_or_fails_explicitly(self):
        invalid = {**editorial(), "metadata_line": "Two Fragments · missing context"}
        for corrected in (True, False):
            with self.subTest(corrected=corrected):
                client = fake_client(invalid, editorial() if corrected else invalid)
                audit = []
                if corrected:
                    result = self.invoke(client, output_type=Editorial, audit=audit)
                    self.assertEqual(result.metadata_line, editorial()["metadata_line"])
                else:
                    with self.assertRaisesRegex(ChainError, "after 2 attempt"):
                        self.invoke(client, output_type=Editorial, audit=audit)
                self.assertEqual(client.responses.create.call_count, 2)
                self.assertEqual(len(audit), 2)

    def test_model_refusal_is_audited_and_never_repaired_into_an_assessment(self):
        response = make_response(
            {},
            output=[
                {
                    "id": "msg_refused",
                    "type": "message",
                    "role": "assistant",
                    "status": "completed",
                    "content": [{"type": "refusal", "refusal": "Cannot evaluate this input."}],
                }
            ],
        )
        client = fake_client(response, relevance())
        audit = []
        with self.assertRaisesRegex(ChainError, "refused.*Cannot evaluate"):
            self.invoke(client, audit=audit)
        client.responses.create.assert_called_once()
        self.assertEqual(len(audit), 1)
        self.assertEqual(audit[0].response_id, response.id)

    def test_incomplete_and_failed_responses_are_audited_without_using_their_text(self):
        for overrides in (
            {"status": "incomplete", "incomplete_details": {"reason": "max_output_tokens"}},
            {"status": "failed", "error": {"code": "server_error", "message": "Try later."}},
        ):
            with self.subTest(status=overrides["status"]):
                response = make_response(relevance(), **overrides)
                client = fake_client(response, relevance())
                audit = []
                with self.assertRaisesRegex(ChainError, str(overrides["status"])):
                    self.invoke(client, audit=audit)
                client.responses.create.assert_called_once()
                self.assertEqual(len(audit), 1)
                self.assertEqual(audit[0].status, overrides["status"])

    def test_unfinished_search_rejects_an_otherwise_valid_assessment(self):
        for status in ("failed", "incomplete", "searching", "in_progress"):
            with self.subTest(search_status=status):
                response = make_response(make_assessment().model_dump())
                output = [item.model_dump(mode="json") for item in response.output]
                output.insert(
                    0,
                    {
                        "id": "ws_failed",
                        "type": "web_search_call",
                        "status": status,
                        "action": {"type": "search", "query": "verification"},
                    },
                )
                client = fake_client(make_response({}, output=output))
                audit = []
                with self.assertRaisesRegex(ChainError, "web search did not complete"):
                    self.invoke(
                        client,
                        output_type=Assessment,
                        settings=ScorerConfig(web_search=True),
                        audit=audit,
                    )
                client.responses.create.assert_called_once()
                self.assertEqual(len(audit), 1)
                self.assertEqual(audit[0].web_search_calls[0]["status"], status)

    def test_citations_sources_and_usage_survive_the_sdk_response_boundary(self):
        response = make_response(make_assessment().model_dump())
        output = [item.model_dump(mode="json") for item in response.output]
        citation = {
            "type": "url_citation",
            "start_index": 0,
            "end_index": 8,
            "title": "Original evidence",
            "url": "https://example.org/evidence",
        }
        output[0]["content"][0]["annotations"] = [citation]
        source = {"type": "url", "url": "https://example.org/additional-source"}
        output.insert(
            0,
            {
                "id": "ws_complete",
                "type": "web_search_call",
                "status": "completed",
                "action": {"type": "search", "queries": ["verification"], "sources": [source]},
            },
        )
        client = fake_client(make_response({}, output=output))
        audit = []
        result = self.invoke(
            client,
            output_type=Assessment,
            settings=ScorerConfig(web_search=True),
            audit=audit,
        )

        self.assertIsInstance(result, Assessment)
        self.assertEqual(audit[0].citations, [citation])
        self.assertEqual(audit[0].web_search_calls[0]["action"]["sources"], [source])
        self.assertEqual(audit[0].web_search_calls[0]["id"], "ws_complete")
        self.assertEqual(audit[0].usage["input_tokens"], 10)
        self.assertEqual(audit[0].usage["output_tokens"], 20)
        self.assertEqual(audit[0].usage["total_tokens"], 30)

    def test_a_response_without_usage_is_still_auditable(self):
        client = fake_client(make_response(relevance(), usage=None))
        audit = []
        self.invoke(client, audit=audit)
        self.assertIsNone(audit[0].usage)
        self.assertEqual(audit[0].citations, [])
        self.assertEqual(audit[0].web_search_calls, [])


if __name__ == "__main__":
    unittest.main()
