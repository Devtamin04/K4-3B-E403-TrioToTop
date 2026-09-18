from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from pydantic import BaseModel, ConfigDict

from app.adapters.evaluator_llm import EvaluatorOutputPayload, LlmEvaluator
from app.llm.errors import LlmInvalidOutputError, LlmPermanentError, LlmTransientError
from app.llm.ollama_client import OllamaStructuredLlmClient
from app.teachback.models import TeachBackState, TopicDefinition

ROOT = Path(__file__).resolve().parents[2]


class SampleOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str


def response(content: str, *, headers: dict[str, str] | None = None) -> httpx.Response:
    return httpx.Response(
        200,
        headers=headers,
        json={
            "model": "configured-model",
            "message": {"role": "assistant", "content": content},
            "done": True,
            "done_reason": "stop",
        },
    )


def make_client(
    handler: httpx.MockTransport,
    *,
    send_format: bool = False,
) -> OllamaStructuredLlmClient:
    return OllamaStructuredLlmClient(
        api_key="test-secret-key",
        base_url="https://ollama.com",
        send_format=send_format,
        http_client=httpx.Client(transport=handler),
    )


def test_cloud_request_embeds_schema_and_validates_content_without_format() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers["Authorization"]
        captured["body"] = json.loads(request.content)
        return response('{"answer":"validated"}', headers={"x-request-id": "request-1"})

    client = make_client(httpx.MockTransport(handler))
    result = client.generate_structured(
        model="configured-model",
        system_prompt="Evaluate only.",
        user_input="Input payload",
        output_type=SampleOutput,
        timeout_seconds=10,
    )

    assert result.parsed == SampleOutput(answer="validated")
    assert result.request_id == "request-1"
    assert captured["url"] == "https://ollama.com/api/chat"
    assert captured["authorization"] == "Bearer test-secret-key"
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["stream"] is False
    assert body["options"] == {"temperature": 0}
    assert "format" not in body
    messages = body["messages"]
    assert isinstance(messages, list)
    assert "Return JSON only" in messages[0]["content"]
    assert '"answer"' in messages[0]["content"]
    assert "test-secret-key" not in json.dumps(body)


def test_format_field_can_be_enabled_for_supported_ollama_runtime() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return response('{"answer":"validated"}')

    client = make_client(httpx.MockTransport(handler), send_format=True)
    client.generate_structured(
        model="configured-model",
        system_prompt="Evaluate only.",
        user_input="Input payload",
        output_type=SampleOutput,
        timeout_seconds=10,
    )

    assert captured["format"] == SampleOutput.model_json_schema()


@pytest.mark.parametrize("content", ["not json", '{"answer":1}', '{"extra":"field"}'])
def test_ignored_format_or_schema_invalid_content_is_rejected(content: str) -> None:
    client = make_client(httpx.MockTransport(lambda request: response(content)))

    with pytest.raises(LlmInvalidOutputError, match="required JSON schema"):
        client.generate_structured(
            model="configured-model",
            system_prompt="Evaluate only.",
            user_input="Input payload",
            output_type=SampleOutput,
            timeout_seconds=10,
        )


def test_incomplete_or_malformed_envelope_is_rejected() -> None:
    responses = iter(
        [
            httpx.Response(
                200,
                json={
                    "model": "configured-model",
                    "message": {"role": "assistant", "content": '{"answer":"x"}'},
                    "done": False,
                },
            ),
            httpx.Response(200, text="not json"),
        ]
    )
    client = make_client(httpx.MockTransport(lambda request: next(responses)))

    with pytest.raises(LlmInvalidOutputError, match="incomplete"):
        client.generate_structured(
            model="configured-model",
            system_prompt="system",
            user_input="input",
            output_type=SampleOutput,
            timeout_seconds=10,
        )
    with pytest.raises(LlmInvalidOutputError, match="chat response"):
        client.generate_structured(
            model="configured-model",
            system_prompt="system",
            user_input="input",
            output_type=SampleOutput,
            timeout_seconds=10,
        )


@pytest.mark.parametrize("status", [408, 409, 425, 429, 500, 503])
def test_retryable_http_statuses_are_transient(status: int) -> None:
    client = make_client(httpx.MockTransport(lambda request: httpx.Response(status)))

    with pytest.raises(LlmTransientError):
        client.generate_structured(
            model="configured-model",
            system_prompt="system",
            user_input="input",
            output_type=SampleOutput,
            timeout_seconds=10,
        )


@pytest.mark.parametrize("status", [400, 401, 403, 404, 422])
def test_non_retryable_http_statuses_are_permanent(status: int) -> None:
    client = make_client(httpx.MockTransport(lambda request: httpx.Response(status)))

    with pytest.raises(LlmPermanentError):
        client.generate_structured(
            model="configured-model",
            system_prompt="system",
            user_input="input",
            output_type=SampleOutput,
            timeout_seconds=10,
        )


def test_network_timeout_is_transient() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    client = make_client(httpx.MockTransport(handler))
    with pytest.raises(LlmTransientError):
        client.generate_structured(
            model="configured-model",
            system_prompt="system",
            user_input="input",
            output_type=SampleOutput,
            timeout_seconds=10,
        )


def test_schema_invalid_cloud_response_uses_llm_evaluator_retry_path(
    topic: TopicDefinition,
) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return response("The server ignored the requested schema.")
        return response(EvaluatorOutputPayload(confidence=0.9).model_dump_json())

    evaluator = LlmEvaluator(
        client=make_client(httpx.MockTransport(handler)),
        model="configured-model",
        prompt_path=ROOT / "app" / "prompts" / "evaluator_v1.md",
        max_attempts=2,
    )
    state = TeachBackState(
        session_id="session",
        topic_id=topic.id,
        topic_version=topic.version,
    )

    result = evaluator.evaluate(topic, state, (), "An off-topic response.")

    assert calls == 2
    assert result.confidence == 0.9
    assert state.turn_count == 0
