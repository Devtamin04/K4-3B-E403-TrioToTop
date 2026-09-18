from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel

from app.llm.interfaces import StructuredLlmResponse, StructuredOutputT


class ScriptedStructuredLlmClient:
    def __init__(self, outcomes: Sequence[BaseModel | Exception]) -> None:
        self._outcomes = list(outcomes)
        self.calls: list[dict[str, Any]] = []

    def generate_structured(
        self,
        *,
        model: str,
        system_prompt: str,
        user_input: str,
        output_type: type[StructuredOutputT],
        timeout_seconds: float,
    ) -> StructuredLlmResponse[StructuredOutputT]:
        self.calls.append(
            {
                "model": model,
                "system_prompt": system_prompt,
                "user_input": user_input,
                "output_type": output_type,
                "timeout_seconds": timeout_seconds,
            }
        )
        if not self._outcomes:
            raise AssertionError("scripted LLM client has no remaining outcome")
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        if not isinstance(outcome, output_type):
            raise AssertionError(
                f"scripted outcome {type(outcome).__name__} is not {output_type.__name__}"
            )
        return StructuredLlmResponse(
            parsed=outcome,
            model=model,
            request_id=f"request-{len(self.calls)}",
        )
