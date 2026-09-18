from __future__ import annotations

from app.teachback.exceptions import InvalidEvaluationError
from app.teachback.models import (
    EvaluationResult,
    Judgment,
    TeachBackState,
    TopicDefinition,
)

STALL_THRESHOLD = 3
"""Số lần hỏi lại cùng một mục tiêu không tiến triển trước khi coi là bế tắc."""

BARREN_TURN_LIMIT = 3
"""Số lượt liên tiếp không có bằng chứng trước khi coi là người học đã ngừng dạy."""


def missing_concepts(topic: TopicDefinition, state: TeachBackState) -> frozenset[str]:
    return topic.required_concept_ids - state.covered_concepts


class StateReducer:
    """Validates per-turn observations and folds them into accumulated state."""

    def apply(
        self,
        topic: TopicDefinition,
        state: TeachBackState,
        result: EvaluationResult,
        latest_user_message: str,
    ) -> TeachBackState:
        expected_turn = state.turn_count + 1
        self._validate(topic, result, latest_user_message, expected_turn)

        covered = set(state.covered_concepts)
        unclear = set(state.unclear_concepts)
        active_misconceptions = set(state.active_misconceptions)

        for concept_id in result.covered:
            covered.add(concept_id)
            unclear.discard(concept_id)

        for concept_id in result.unclear:
            covered.discard(concept_id)
            unclear.add(concept_id)

        detected_concepts = {
            topic.misconception(item_id).concept_id for item_id in result.misconceptions
        }
        for misconception_id in result.misconceptions:
            active_misconceptions.add(misconception_id)
        for concept_id in detected_concepts:
            covered.discard(concept_id)
            unclear.discard(concept_id)

        for misconception_id in result.resolved_misconceptions:
            active_misconceptions.discard(misconception_id)

        # Any incorrect evidence is a conservative contradiction, even when it
        # does not match a curated misconception. It reopens the concept.
        for evidence in result.evidence:
            if evidence.judgment is Judgment.INCORRECT:
                covered.discard(evidence.concept_id)
                if evidence.concept_id not in detected_concepts:
                    unclear.add(evidence.concept_id)

        made_progress = bool(
            covered != set(state.covered_concepts)
            or unclear != set(state.unclear_concepts)
            or active_misconceptions != set(state.active_misconceptions)
        )
        attempts, stalled = self._track_target_attempts(state, made_progress)

        return state.model_copy(
            update={
                "covered_concepts": frozenset(covered),
                "unclear_concepts": frozenset(unclear),
                "active_misconceptions": frozenset(active_misconceptions),
                "evidence": (*state.evidence, *result.evidence),
                "turn_count": expected_turn,
                "attempts_per_target": attempts,
                "stalled_targets": stalled,
                "barren_turns": 0 if result.evidence else state.barren_turns + 1,
            }
        )

    @staticmethod
    def _track_target_attempts(
        state: TeachBackState, made_progress: bool
    ) -> tuple[dict[str, int], frozenset[str]]:
        """Đếm số lần hỏi lại cùng một mục tiêu mà trạng thái không đổi.

        Tiến triển làm bộ đếm về 0, nên chỉ những lần lặp thật sự vô ích mới
        tích lũy và khiến mục tiêu bị đánh dấu bế tắc.
        """

        attempts = dict(state.attempts_per_target)
        target = state.current_target
        if target is None:
            return attempts, state.stalled_targets
        if made_progress:
            attempts.pop(target.id, None)
            return attempts, state.stalled_targets - {target.id}

        attempts[target.id] = attempts.get(target.id, 0) + 1
        if attempts[target.id] >= STALL_THRESHOLD:
            return attempts, state.stalled_targets | {target.id}
        return attempts, state.stalled_targets

    def _validate(
        self,
        topic: TopicDefinition,
        result: EvaluationResult,
        latest_user_message: str,
        expected_turn: int,
    ) -> None:
        concept_ids = {concept.id for concept in topic.concepts}
        misconception_ids = {item.id for item in topic.misconceptions}

        unknown_concepts = (set(result.covered) | set(result.unclear)) - concept_ids
        unknown_evidence = {item.concept_id for item in result.evidence} - concept_ids
        unknown_misconceptions = (
            set(result.misconceptions) | set(result.resolved_misconceptions)
        ) - misconception_ids
        if unknown_concepts or unknown_evidence or unknown_misconceptions:
            raise InvalidEvaluationError(
                "evaluation references unknown IDs: "
                f"concepts={sorted(unknown_concepts | unknown_evidence)}, "
                f"misconceptions={sorted(unknown_misconceptions)}"
            )

        for evidence in result.evidence:
            if evidence.turn != expected_turn:
                raise InvalidEvaluationError(
                    f"evidence turn {evidence.turn} does not match expected turn {expected_turn}"
                )
            if evidence.user_quote not in latest_user_message:
                raise InvalidEvaluationError("evidence quote must occur in the latest user message")

        correct_ids = {
            item.concept_id for item in result.evidence if item.judgment is Judgment.CORRECT
        }
        unclear_ids = {
            item.concept_id for item in result.evidence if item.judgment is Judgment.UNCLEAR
        }
        incorrect_ids = {
            item.concept_id for item in result.evidence if item.judgment is Judgment.INCORRECT
        }
        if not set(result.covered) <= correct_ids:
            raise InvalidEvaluationError("every covered concept requires correct evidence")
        if not set(result.unclear) <= unclear_ids:
            raise InvalidEvaluationError("every unclear concept requires unclear evidence")

        for misconception_id in result.misconceptions:
            concept_id = topic.misconception(misconception_id).concept_id
            if concept_id not in incorrect_ids:
                raise InvalidEvaluationError(
                    f"detected misconception {misconception_id} requires incorrect evidence"
                )
        for misconception_id in result.resolved_misconceptions:
            concept_id = topic.misconception(misconception_id).concept_id
            if concept_id not in result.covered:
                raise InvalidEvaluationError(
                    f"resolved misconception {misconception_id} requires its concept to be covered"
                )

        if result.recommended_target is not None:
            all_ids = concept_ids | misconception_ids
            if result.recommended_target not in all_ids:
                raise InvalidEvaluationError("recommended target references an unknown ID")
