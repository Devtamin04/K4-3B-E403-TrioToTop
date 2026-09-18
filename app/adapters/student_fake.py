from __future__ import annotations

from collections.abc import Sequence

from app.teachback.models import (
    Action,
    Message,
    PolicyDecision,
    TeachBackState,
    TopicDefinition,
)


class DeterministicStudentGenerator:
    def opening(self, topic: TopicDefinition) -> str:
        return topic.opening_question

    def generate(
        self,
        topic: TopicDefinition,
        state: TeachBackState,
        decision: PolicyDecision,
        history: Sequence[Message],
    ) -> str:
        del state, history
        if decision.action is Action.FINISH:
            return topic.completion_message
        if decision.action is Action.HALT:
            return topic.halt_message
        if decision.target is None:  # Protected by PolicyDecision validation.
            raise ValueError("non-FINISH decision requires a target")
        if decision.action is Action.CHALLENGE:
            return topic.misconception(decision.target.id).challenge_question
        concept = topic.concept(decision.target.id)
        if decision.action is Action.CLARIFY:
            return concept.clarify_question
        return concept.probe_question
