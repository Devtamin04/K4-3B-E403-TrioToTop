from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, TypeVar

from pydantic import BaseModel

StructuredOutputT = TypeVar("StructuredOutputT", bound=BaseModel)


@dataclass(frozen=True, slots=True)
class StructuredLlmResponse[StructuredOutputT: BaseModel]:
    parsed: StructuredOutputT
    model: str
    request_id: str | None = None


class StructuredLlmClient(Protocol):
    def generate_structured(
        self,
        *,
        model: str,
        system_prompt: str,
        user_input: str,
        output_type: type[StructuredOutputT],
        timeout_seconds: float,
    ) -> StructuredLlmResponse[StructuredOutputT]: ...
