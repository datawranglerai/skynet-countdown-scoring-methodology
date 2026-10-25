"""A small structured-output chain, with optional hosted search for the scorer."""

import json
from typing import Any

from openai import OpenAI
from pydantic import BaseModel, ValidationError

from .config import ChainConfig, ScorerConfig
from .models import AgentRun


class ChainError(RuntimeError):
    """The model did not provide a usable assessment; never substitute a score."""


def run_chain[Output: BaseModel](
    client: OpenAI,
    *,
    instructions: str,
    payload: dict[str, Any],
    output_type: type[Output],
    settings: ChainConfig,
    audit: list[AgentRun],
) -> Output:
    """Request structured output and retry responses that fail schema validation.

    Each received response is appended to ``audit`` before its content is checked.
    Only schema-validation failures trigger correction requests, up to
    ``settings.max_iterations`` total attempts. Hosted search is enabled only
    when requested by a ``ScorerConfig``; transport retries belong to the client.

    :param client: OpenAI client used to send Responses API requests.
    :type client: openai.OpenAI
    :param instructions: Stage instructions, extended with the applicable evidence rule.
    :type instructions: str
    :param payload: JSON-serializable evidence supplied as the user message.
    :type payload: dict[str, typing.Any]
    :param output_type: Pydantic model defining the requested JSON schema and validation.
    :type output_type: type[Output]
    :param settings: Model, reasoning, token and attempt limits, plus optional search settings.
    :type settings: ChainConfig
    :param audit: Caller-owned list extended in place with each received response's metadata.
    :type audit: list[AgentRun]
    :return: The first response that satisfies the output model's validation rules.
    :rtype: Output
    :raises ChainError: If the model refuses, a response or search is incomplete,
        or structured output remains invalid after all permitted attempts.
    :raises openai.OpenAIError: If an API request fails after the client's retries.
    :raises TypeError: If the payload contains values that cannot be serialized to JSON.
    """
    search_enabled = isinstance(settings, ScorerConfig) and settings.web_search
    source_rule = (
        "Web search is available for checking this supplied story. Distinguish retrieved "
        "evidence from supplied evidence and cite any additional sources in your rationales. "
        "Do not discover or add other stories."
        if search_enabled
        else "No retrieval tools are available. Use only the evidence in the supplied input. "
        "A source URL does not mean its page has been read. Note missing evidence."
    )
    request: dict[str, Any] = {
        "model": settings.model,
        "instructions": instructions + "\n\n" + source_rule,
        "input": [{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
        "text": {
            "format": {
                "type": "json_schema",
                "name": output_type.__name__,
                "schema": output_type.model_json_schema(),
                "strict": True,
            }
        },
        "max_output_tokens": settings.max_output_tokens,
        "store": False,
    }
    if settings.reasoning_effort != "omit":
        request["reasoning"] = {"effort": settings.reasoning_effort}
    if isinstance(settings, ScorerConfig) and search_enabled:
        request["tools"] = [
            {
                "type": "web_search",
                "search_context_size": settings.web_search_context_size,
            }
        ]
        request["max_tool_calls"] = settings.max_tool_calls
        request["include"] = ["web_search_call.action.sources"]

    for attempt in range(settings.max_iterations):
        response = client.responses.create(**request)
        citations: list[dict[str, Any]] = []
        searches: list[dict[str, Any]] = []
        refusals: list[str] = []
        for item in response.output:
            if item.type == "web_search_call":
                searches.append(item.model_dump(mode="json"))
            elif item.type == "message":
                for part in item.content:
                    if part.type == "refusal":
                        refusals.append(part.refusal)
                    elif part.type == "output_text":
                        citations.extend(a.model_dump(mode="json") for a in part.annotations)
        audit.append(
            AgentRun(
                response_id=response.id,
                model=response.model,
                status=response.status or "unknown",
                usage=response.usage.model_dump(mode="json") if response.usage else None,
                citations=citations,
                web_search_calls=searches,
            )
        )
        if refusals:
            raise ChainError("Model refused the request: " + "; ".join(refusals))
        if response.status != "completed":
            details = response.incomplete_details or response.error
            raise ChainError(f"Response was {response.status}: {details}")
        if any(call["status"] != "completed" for call in searches):
            raise ChainError("A web search did not complete; the assessment needs review.")
        try:
            return output_type.model_validate_json(response.output_text)
        except ValidationError as exc:
            if attempt + 1 == settings.max_iterations:
                raise ChainError(
                    f"Invalid structured output after {settings.max_iterations} attempt(s)."
                ) from exc
            errors = exc.errors(include_input=False, include_url=False, include_context=False)
            request["input"].extend(
                [
                    {"role": "assistant", "content": response.output_text},
                    {
                        "role": "user",
                        "content": (
                            "Correct the JSON to satisfy the schema and these validation errors: "
                            + json.dumps(errors)
                        ),
                    },
                ]
            )
    raise AssertionError("max_iterations is validated as positive")
