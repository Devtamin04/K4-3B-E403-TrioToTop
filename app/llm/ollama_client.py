from __future__ import annotations

import json
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.llm.errors import LlmInvalidOutputError, LlmPermanentError, LlmTransientError
from app.llm.interfaces import StructuredLlmResponse, StructuredOutputT


class _OllamaMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    role: Literal["assistant"]
    content: str


class _OllamaChatResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    model: str = Field(min_length=1)
    message: _OllamaMessage
    done: bool
    done_reason: str | None = None


class OllamaStructuredLlmClient:
    """Strict JSON client for Ollama's native ``/api/chat`` endpoint.

    JSON Schema is always included in the prompt. Sending the schema through
    Ollama's ``format`` field is optional because Ollama Cloud does not
    currently guarantee server-side structured-output enforcement.
    """

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://ollama.com",
        send_format: bool = False,
        http_client: httpx.Client | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("Ollama API key must not be empty")
        self._endpoint = _chat_endpoint(base_url)
        self._api_key = api_key
        self._send_format = send_format
        self._client = http_client or httpx.Client()

    def generate_structured(
        self,
        *,
        model: str,
        system_prompt: str,
        user_input: str,
        output_type: type[StructuredOutputT],
        timeout_seconds: float,
    ) -> StructuredLlmResponse[StructuredOutputT]:
        schema = output_type.model_json_schema()
        schema_json = json.dumps(schema, ensure_ascii=False, separators=(",", ":"))
        json_instruction = (
            "Return JSON only: exactly one JSON object, with no Markdown fences, "
            "commentary, or text outside the object. The object must validate "
            f"against this JSON Schema:\n{schema_json}"
        )
        body: dict[str, object] = {
            "model": model,
            "messages": [
                {"role": "system", "content": f"{system_prompt}\n\n{json_instruction}"},
                {"role": "user", "content": user_input},
            ],
            "stream": False,
            "options": {"temperature": 0},
        }
        if self._send_format:
            body["format"] = schema

        try:
            response = self._client.post(
                self._endpoint,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
                timeout=timeout_seconds,
            )
        except (httpx.TimeoutException, httpx.NetworkError) as error:
            raise LlmTransientError("Ollama request failed transiently") from error
        except httpx.HTTPError as error:
            raise LlmPermanentError("Ollama request could not be sent") from error

        if response.status_code in {408, 409, 425, 429} or response.status_code >= 500:
            raise LlmTransientError(f"Ollama returned HTTP {response.status_code}")
        if response.status_code >= 400:
            raise LlmPermanentError(f"Ollama rejected the request with HTTP {response.status_code}")

        try:
            envelope = _OllamaChatResponse.model_validate(response.json())
        except (ValueError, ValidationError) as error:
            raise LlmInvalidOutputError("Ollama returned an invalid chat response") from error
        if not envelope.done:
            raise LlmInvalidOutputError("Ollama returned an incomplete non-streaming response")

        try:
            parsed = output_type.model_validate_json(envelope.message.content)
        except (ValueError, ValidationError) as error:
            raise LlmInvalidOutputError(
                "Ollama message content did not match the required JSON schema"
            ) from error

        return StructuredLlmResponse(
            parsed=parsed,
            model=envelope.model,
            request_id=response.headers.get("x-request-id"),
        )


def _chat_endpoint(base_url: str) -> str:
    try:
        url = httpx.URL(base_url)
    except httpx.InvalidURL as error:
        raise ValueError("OLLAMA_BASE_URL must be a valid HTTP(S) URL") from error
    if url.scheme not in {"http", "https"} or not url.host:
        raise ValueError("OLLAMA_BASE_URL must be a valid HTTP(S) URL")
    if url.query or url.fragment:
        raise ValueError("OLLAMA_BASE_URL must not contain a query or fragment")
    return f"{str(url).rstrip('/')}/api/chat"
