"""Modelled API responses for exercising the real structured-output boundary."""

import json
from typing import Any
from unittest.mock import Mock

from openai.types.responses import Response


def make_response(value: dict[str, Any] | str, **overrides: Any) -> Response:
    return Response.model_validate(
        {
            "id": "resp_test",
            "created_at": 0,
            "object": "response",
            "model": "gpt-5.4",
            "status": "completed",
            "error": None,
            "incomplete_details": None,
            "instructions": None,
            "metadata": {},
            "parallel_tool_calls": False,
            "temperature": None,
            "top_p": None,
            "tool_choice": "auto",
            "tools": [],
            "output": [
                {
                    "id": "msg_test",
                    "type": "message",
                    "role": "assistant",
                    "status": "completed",
                    "content": [
                        {
                            "type": "output_text",
                            "text": value if isinstance(value, str) else json.dumps(value),
                            "annotations": [],
                            "logprobs": [],
                        }
                    ],
                }
            ],
            "usage": {
                "input_tokens": 10,
                "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
                "output_tokens": 20,
                "output_tokens_details": {"reasoning_tokens": 0},
                "total_tokens": 30,
            },
            **overrides,
        }
    )


def fake_client(*values: dict[str, Any] | str | Response | Exception) -> Mock:
    client = Mock()
    client.responses.create.side_effect = [
        item if isinstance(item, (Response, Exception)) else make_response(item) for item in values
    ]
    return client


def relevance(relevant: bool = True, score: int = 8) -> dict[str, Any]:
    return {
        "relevant_to_skynet": relevant,
        "relevance_score": score,
        "relevance_rationale": "The supplied evidence supports this screening decision.",
        "primary_dimension": "trifecta" if relevant else "none",
    }


def editorial() -> dict[str, str]:
    return {
        "headline": "The Inbox Got Production Permissions",
        "metadata_line": "inbox agent · production access · daily review",
        "the_story": "An agent processed external emails. It could update private records.",
        "our_take": "Daily review leaves a gap between action and oversight.\n\nThe permissions matter.",
    }
