from app.teachback.models import (
    Action,
    PolicyDecision,
    SessionStatus,
    Target,
    TargetKind,
    TeachBackState,
    TopicDefinition,
)
from app.teachback.state import BARREN_TURN_LIMIT, missing_concepts


class PolicyEngine:
    def choose(self, topic: TopicDefinition, state: TeachBackState) -> PolicyDecision:
        if state.status is not SessionStatus.ACTIVE:
            raise ValueError("policy can only run for an active session")

        # Đổi sang mục tiêu khác trước đã: người học bí một khái niệm không có
        # nghĩa là bí cả chủ đề, nên còn khái niệm chưa thử thì chưa dừng.
        decision = self._next_target(topic, state, state.stalled_targets)
        if decision is not None:
            return decision

        # Đã thử hết mọi mục tiêu mà vẫn bế tắc thì mới dừng.
        if self._next_target(topic, state, frozenset()) is not None:
            reason = (
                "learner_stopped_teaching"
                if state.barren_turns >= BARREN_TURN_LIMIT
                else "all_targets_stalled"
            )
            return PolicyDecision(action=Action.HALT, target=None, reason_code=reason)

        return PolicyDecision(
            action=Action.FINISH,
            target=None,
            reason_code="all_requirements_satisfied",
        )

    def _next_target(
        self, topic: TopicDefinition, state: TeachBackState, skip: frozenset[str]
    ) -> PolicyDecision | None:
        misconception = self._first_misconception(topic, state.active_misconceptions - skip)
        if misconception is not None:
            return PolicyDecision(
                action=Action.CHALLENGE,
                target=Target(kind=TargetKind.MISCONCEPTION, id=misconception),
                reason_code="active_misconception",
            )

        required_unclear = state.unclear_concepts & topic.required_concept_ids
        concept = self._first_concept(topic, required_unclear - skip)
        if concept is not None:
            return PolicyDecision(
                action=Action.CLARIFY,
                target=Target(kind=TargetKind.CONCEPT, id=concept),
                reason_code="unclear_required_concept",
            )

        concept = self._first_concept(topic, missing_concepts(topic, state) - skip)
        if concept is not None:
            return PolicyDecision(
                action=Action.PROBE,
                target=Target(kind=TargetKind.CONCEPT, id=concept),
                reason_code="missing_required_concept",
            )
        return None

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
