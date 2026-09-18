from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.adapters.evaluator_llm import EvaluatorOutputPayload
from app.teachback.models import Message, MessageRole, TeachBackState, TopicDefinition


class EvalModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PriorState(EvalModel):
    turn_count: int = Field(default=0, ge=0)
    covered_concepts: list[str] = Field(default_factory=list)
    unclear_concepts: list[str] = Field(default_factory=list)
    active_misconceptions: list[str] = Field(default_factory=list)


class HistoryMessage(EvalModel):
    role: MessageRole
    content: str = Field(min_length=1)
    turn_number: int = Field(ge=0)


class RegressionCase(EvalModel):
    id: str = Field(min_length=1)
    category: str = Field(min_length=1)
    topic_id: str = Field(min_length=1)
    prior_state: PriorState = Field(default_factory=PriorState)
    history: list[HistoryMessage] = Field(default_factory=list)
    latest_user_message: str = Field(min_length=1)
    expected: EvaluatorOutputPayload
    completion_safe: bool

    def make_state(self, topic: TopicDefinition) -> TeachBackState:
        return TeachBackState(
            session_id=f"eval-{self.id}",
            topic_id=topic.id,
            topic_version=topic.version,
            covered_concepts=frozenset(self.prior_state.covered_concepts),
            unclear_concepts=frozenset(self.prior_state.unclear_concepts),
            active_misconceptions=frozenset(self.prior_state.active_misconceptions),
            turn_count=self.prior_state.turn_count,
        )

    def make_history(self) -> tuple[Message, ...]:
        timestamp = datetime(2026, 1, 1, tzinfo=UTC)
        return tuple(
            Message(
                id=f"{self.id}-history-{index}",
                role=item.role,
                content=item.content,
                turn_number=item.turn_number,
                created_at=timestamp,
            )
            for index, item in enumerate(self.history)
        )


def load_dataset(path: Path) -> list[RegressionCase]:
    try:
        raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
        cases = [RegressionCase.model_validate(item) for item in raw]
    except (OSError, TypeError, yaml.YAMLError, ValidationError) as error:
        raise ValueError(f"invalid evaluator regression dataset {path}: {error}") from error
    ids = [case.id for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("evaluator regression case IDs must be unique")
    return cases
