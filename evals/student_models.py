from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.teachback.models import (
    Action,
    Message,
    MessageRole,
    PolicyDecision,
    Target,
    TargetKind,
    TeachBackState,
    TopicDefinition,
)


class EvalModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HistoryMessage(EvalModel):
    role: MessageRole
    content: str = Field(min_length=1)
    turn_number: int = Field(ge=0)


class CaseType(StrEnum):
    """Eval-only classification; the runtime student never sees this."""

    NORMAL = "normal"
    ADVERSARIAL = "adversarial"


class StudentCase(EvalModel):
    """A fixed policy decision whose phrasing the student must produce."""

    id: str = Field(min_length=1)
    category: str = Field(min_length=1)
    case_type: CaseType = CaseType.NORMAL
    topic_id: str = Field(min_length=1)
    action: Action
    target_kind: TargetKind
    target_id: str = Field(min_length=1)
    history: list[HistoryMessage] = Field(default_factory=list)
    latest_user_message: str = Field(min_length=1)

    def make_decision(self) -> PolicyDecision:
        return PolicyDecision(
            action=self.action,
            target=Target(kind=self.target_kind, id=self.target_id),
            reason_code="eval_fixture",
        )

    def make_state(self, topic: TopicDefinition) -> TeachBackState:
        return TeachBackState(
            session_id=f"student-eval-{self.id}",
            topic_id=topic.id,
            topic_version=topic.version,
            turn_count=len(self.history),
        )

    def make_history(self) -> tuple[Message, ...]:
        timestamp = datetime(2026, 1, 1, tzinfo=UTC)
        messages = [
            Message(
                id=f"{self.id}-history-{index}",
                role=item.role,
                content=item.content,
                turn_number=item.turn_number,
                created_at=timestamp,
            )
            for index, item in enumerate(self.history)
        ]
        messages.append(
            Message(
                id=f"{self.id}-latest",
                role=MessageRole.HUMAN_TEACHER,
                content=self.latest_user_message,
                turn_number=len(self.history) + 1,
                created_at=timestamp,
            )
        )
        return tuple(messages)

    def curated_question(self, topic: TopicDefinition) -> str:
        if self.target_kind is TargetKind.MISCONCEPTION:
            return topic.misconception(self.target_id).challenge_question
        concept = topic.concept(self.target_id)
        if self.action is Action.CLARIFY:
            return concept.clarify_question
        return concept.probe_question

    def expected_answer(self, topic: TopicDefinition) -> str:
        if self.target_kind is TargetKind.MISCONCEPTION:
            return topic.misconception(self.target_id).correction
        return topic.concept(self.target_id).description


def load_student_dataset(path: Path) -> list[StudentCase]:
    try:
        raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
        cases = [StudentCase.model_validate(item) for item in raw]
    except (OSError, TypeError, yaml.YAMLError, ValidationError) as error:
        raise ValueError(f"invalid student regression dataset {path}: {error}") from error
    ids = [case.id for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("student regression case IDs must be unique")
    return cases
