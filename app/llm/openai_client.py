from __future__ import annotations

import openai
from openai import OpenAI
from pydantic import ValidationError

from app.llm.errors import (
    LlmInvalidOutputError,
    LlmPermanentError,
    LlmRefusalError,
    LlmTransientError,
)
from app.llm.interfaces import StructuredLlmResponse, StructuredOutputT


class OpenAiStructuredLlmClient:
    """OpenAI Responses adapter with SDK retries disabled.

    Retry ownership belongs to LlmEvaluator so the total attempt count is
    explicit and provider-independent.
    """

    def __init__(self, api_key: str) -> None:
        self._client = OpenAI(api_key=api_key, max_retries=0)

    def generate_structured(
        self,
        *,
        model: str,
        system_prompt: str,
        user_input: str,
        output_type: type[StructuredOutputT],
        timeout_seconds: float,
    ) -> StructuredLlmResponse[StructuredOutputT]:
        try:
            response = self._client.responses.parse(
                model=model,
                instructions=system_prompt,
                input=user_input,
                text_format=output_type,
                timeout=timeout_seconds,
            )
        except (
            openai.APITimeoutError,
            openai.APIConnectionError,
            openai.RateLimitError,
            openai.InternalServerError,
            openai.ConflictError,
        ) as error:
            raise LlmTransientError("OpenAI request failed transiently") from error
        except (
            openai.LengthFinishReasonError,
            openai.APIResponseValidationError,
            ValidationError,
        ) as error:
            raise LlmInvalidOutputError("OpenAI returned invalid structured output") from error
        except openai.ContentFilterFinishReasonError as error:
            raise LlmRefusalError("OpenAI declined to produce the evaluation") from error
        except (
            openai.AuthenticationError,
            openai.PermissionDeniedError,
            openai.BadRequestError,
            openai.NotFoundError,
            openai.UnprocessableEntityError,
        ) as error:
            raise LlmPermanentError("OpenAI rejected the evaluator request") from error
        except openai.APIStatusError as error:
            if error.status_code >= 500 or error.status_code in {408, 409, 429}:
                raise LlmTransientError("OpenAI request failed transiently") from error
            raise LlmPermanentError("OpenAI rejected the evaluator request") from error
        except openai.OpenAIError as error:
            raise LlmPermanentError("OpenAI evaluator request failed") from error

        parsed = response.output_parsed
        if parsed is None:
            raise LlmRefusalError("OpenAI returned no parsed evaluation")

        return StructuredLlmResponse(
            parsed=parsed,
            model=response.model,
            request_id=getattr(response, "_request_id", None),
        )
