from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.teachback.models import (
    EvaluationResult,
    Evidence,
    Message,
    TeachBackState,
    TopicDefinition,
)

logger = logging.getLogger(__name__)


class _FixtureEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    concept_id: str
    user_quote: str
    judgment: str
    explanation: str
    confidence: float = Field(ge=0, le=1)


class _FixtureResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    covered: list[str] = Field(default_factory=list)
    unclear: list[str] = Field(default_factory=list)
    misconceptions: list[str] = Field(default_factory=list)
    resolved_misconceptions: list[str] = Field(default_factory=list)
    evidence: list[_FixtureEvidence] = Field(default_factory=list)
    recommended_target: str | None = None
    confidence: float = Field(ge=0, le=1)


class _FixtureCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    topic_id: str
    user_message: str
    result: _FixtureResult


class FixtureEvaluator:
    """Exact-match fake evaluator; it performs no language interpretation."""

    def __init__(self, fixture_path: Path) -> None:
        try:
            raw: Any = yaml.safe_load(fixture_path.read_text(encoding="utf-8"))
            cases = [_FixtureCase.model_validate(item) for item in raw]
        except (OSError, TypeError, yaml.YAMLError, ValidationError) as error:
            raise ValueError(f"invalid evaluator fixture {fixture_path}: {error}") from error

        self._cases: dict[tuple[str, str], _FixtureCase] = {}
        for case in cases:
            key = (case.topic_id, case.user_message)
            if key in self._cases:
                raise ValueError(f"duplicate evaluator fixture for {key!r}")
            self._cases[key] = case

    def evaluate(
        self,
        topic: TopicDefinition,
        state: TeachBackState,
        history: Sequence[Message],
        latest_user_message: str,
    ) -> EvaluationResult:
        del history
        case = self._cases.get((topic.id, latest_user_message))
        if case is None:
            logger.warning(
                "Fake evaluator has no fixture for topic=%s message=%r; "
                "returning empty observation",
                topic.id,
                latest_user_message,
            )
            return EvaluationResult(confidence=0)

        result = case.result
        evidence = [
            Evidence.model_validate({**item.model_dump(), "turn": state.turn_count + 1})
            for item in result.evidence
        ]
        return EvaluationResult(
            covered=result.covered,
            unclear=result.unclear,
            misconceptions=result.misconceptions,
            resolved_misconceptions=result.resolved_misconceptions,
            evidence=evidence,
            recommended_target=result.recommended_target,
            confidence=result.confidence,
        )
