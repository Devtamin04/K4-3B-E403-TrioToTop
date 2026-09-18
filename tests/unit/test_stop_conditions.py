from __future__ import annotations

from pathlib import Path

from app.adapters.topics_yaml import YamlTopicRepository
from app.teachback.models import (
    Action,
    EvaluationResult,
    Evidence,
    Judgment,
    Target,
    TargetKind,
    TeachBackState,
    TopicDefinition,
)
from app.teachback.policy import PolicyEngine
from app.teachback.state import BARREN_TURN_LIMIT, STALL_THRESHOLD, StateReducer

ROOT = Path(__file__).resolve().parents[2]
MESSAGE = "Mình không biết."


def _topic() -> TopicDefinition:
    return YamlTopicRepository(ROOT / "knowledge").get("context_window")


def _state(topic: TopicDefinition, **overrides: object) -> TeachBackState:
    base: dict[str, object] = {
        "session_id": "s",
        "topic_id": topic.id,
        "topic_version": topic.version,
    }
    base.update(overrides)
    return TeachBackState.model_validate(base)


def _empty_result() -> EvaluationResult:
    return EvaluationResult(confidence=0.5)


def test_barren_turns_accumulate_then_halt() -> None:
    topic = _topic()
    reducer = StateReducer()
    state = _state(topic)

    for _ in range(BARREN_TURN_LIMIT):
        state = reducer.apply(topic, state, _empty_result(), MESSAGE)

    assert state.barren_turns == BARREN_TURN_LIMIT
    decision = PolicyEngine().choose(topic, state)
    assert decision.action is Action.HALT
    assert decision.reason_code == "learner_stopped_teaching"
    assert decision.target is None


def test_evidence_resets_barren_counter() -> None:
    topic = _topic()
    reducer = StateReducer()
    state = _state(topic, barren_turns=2)
    message = "Giới hạn được đếm bằng token."
    result = EvaluationResult(
        covered=["token_unit"],
        evidence=[
            Evidence(
                concept_id="token_unit",
                user_quote="đếm bằng token",
                judgment=Judgment.CORRECT,
                explanation="ok",
                confidence=0.9,
                turn=1,
            )
        ],
        confidence=0.9,
    )

    assert reducer.apply(topic, state, result, message).barren_turns == 0


def test_repeating_a_target_without_progress_marks_it_stalled() -> None:
    topic = _topic()
    reducer = StateReducer()
    state = _state(topic, current_target=Target(kind=TargetKind.CONCEPT, id="token_unit"))

    for _ in range(STALL_THRESHOLD):
        state = reducer.apply(topic, state, _empty_result(), MESSAGE)

    assert "token_unit" in state.stalled_targets


def test_policy_skips_a_stalled_target() -> None:
    topic = _topic()
    state = _state(topic, stalled_targets=frozenset({"token_unit"}))

    decision = PolicyEngine().choose(topic, state)

    assert decision.action is Action.PROBE
    assert decision.target is not None
    assert decision.target.id != "token_unit"


def test_policy_halts_when_every_target_is_stalled() -> None:
    topic = _topic()
    state = _state(topic, stalled_targets=topic.required_concept_ids)

    decision = PolicyEngine().choose(topic, state)

    assert decision.action is Action.HALT
    assert decision.reason_code == "all_targets_stalled"


def test_progress_clears_the_stall_mark() -> None:
    topic = _topic()
    message = "Giới hạn được đếm bằng token."
    state = _state(
        topic,
        current_target=Target(kind=TargetKind.CONCEPT, id="token_unit"),
        stalled_targets=frozenset({"token_unit"}),
        attempts_per_target={"token_unit": STALL_THRESHOLD},
    )
    result = EvaluationResult(
        covered=["token_unit"],
        evidence=[
            Evidence(
                concept_id="token_unit",
                user_quote="đếm bằng token",
                judgment=Judgment.CORRECT,
                explanation="ok",
                confidence=0.9,
                turn=1,
            )
        ],
        confidence=0.9,
    )

    updated = StateReducer().apply(topic, state, result, message)

    assert "token_unit" not in updated.stalled_targets
    assert "token_unit" not in updated.attempts_per_target


def test_halt_is_not_completion() -> None:
    """HALT phải khác FINISH, nếu không sẽ tái lập lỗi false-completion."""

    topic = _topic()
    state = _state(topic, barren_turns=BARREN_TURN_LIMIT)

    decision = PolicyEngine().choose(topic, state)

    assert decision.action is not Action.FINISH
    assert state.covered_concepts != topic.required_concept_ids


def test_finish_still_wins_when_everything_is_covered() -> None:
    topic = _topic()
    state = _state(topic, covered_concepts=topic.required_concept_ids)

    assert PolicyEngine().choose(topic, state).action is Action.FINISH
