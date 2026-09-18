from app.teachback.models import (
    Action,
    PolicyDecision,
    SessionStatus,
    Target,
    TargetKind,
    TeachBackState,
    TopicDefinition,
)
from app.teachback.state import missing_concepts


class PolicyEngine:
    def choose(self, topic: TopicDefinition, state: TeachBackState) -> PolicyDecision:
        if state.status is not SessionStatus.ACTIVE:
            raise ValueError("policy can only run for an active session")

        misconception = self._first_misconception(topic, state.active_misconceptions)
        if misconception is not None:
            return PolicyDecision(
                action=Action.CHALLENGE,
                target=Target(kind=TargetKind.MISCONCEPTION, id=misconception),
                reason_code="active_misconception",
            )

        required_unclear = state.unclear_concepts & topic.required_concept_ids
        concept = self._first_concept(topic, required_unclear)
        if concept is not None:
            return PolicyDecision(
                action=Action.CLARIFY,
                target=Target(kind=TargetKind.CONCEPT, id=concept),
                reason_code="unclear_required_concept",
            )

        concept = self._first_concept(topic, missing_concepts(topic, state))
        if concept is not None:
            return PolicyDecision(
                action=Action.PROBE,
                target=Target(kind=TargetKind.CONCEPT, id=concept),
                reason_code="missing_required_concept",
            )

        return PolicyDecision(
            action=Action.FINISH,
            target=None,
            reason_code="all_requirements_satisfied",
        )

    @staticmethod
    def _first_concept(topic: TopicDefinition, candidates: frozenset[str]) -> str | None:
        ordered = sorted(
            enumerate(topic.concepts),
            key=lambda item: (item[1].priority, item[0]),
        )
        return next((concept.id for _, concept in ordered if concept.id in candidates), None)

    @staticmethod
    def _first_misconception(topic: TopicDefinition, candidates: frozenset[str]) -> str | None:
        ordered = sorted(
            enumerate(topic.misconceptions),
            key=lambda item: (item[1].priority, item[0]),
        )
        return next((item.id for _, item in ordered if item.id in candidates), None)
