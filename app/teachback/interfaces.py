from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from app.teachback.models import (
    EvaluationResult,
    Message,
    PolicyDecision,
    TeachBackSession,
    TeachBackState,
    TopicDefinition,
)


class Evaluator(Protocol):
    def evaluate(
        self,
        topic: TopicDefinition,
        state: TeachBackState,
        history: Sequence[Message],
        latest_user_message: str,
    ) -> EvaluationResult: ...


class StudentGenerator(Protocol):
    def opening(self, topic: TopicDefinition) -> str: ...

    def generate(
        self,
        topic: TopicDefinition,
        state: TeachBackState,
        decision: PolicyDecision,
        history: Sequence[Message],
    ) -> str: ...


class TopicRepository(Protocol):
    def get(self, topic_id: str) -> TopicDefinition: ...

    def list_topics(self) -> list[TopicDefinition]: ...


class SessionRepository(Protocol):
    def create(self, session: TeachBackSession) -> None: ...

    def get(self, session_id: str) -> TeachBackSession: ...

    def save(self, session: TeachBackSession) -> None: ...
