import pytest

from app.teachback.exceptions import InvalidEvaluationError
from app.teachback.models import (
    EvaluationResult,
    Evidence,
    Judgment,
    TeachBackState,
    TopicDefinition,
)
from app.teachback.state import StateReducer, missing_concepts


def state_for(topic: TopicDefinition) -> TeachBackState:
    return TeachBackState(session_id="session", topic_id=topic.id, topic_version=topic.version)


def evidence(concept_id: str, judgment: Judgment, quote: str, turn: int) -> Evidence:
    return Evidence(
        concept_id=concept_id,
        user_quote=quote,
        judgment=judgment,
        explanation="Test evidence",
        confidence=1,
        turn=turn,
    )


def test_correct_evidence_covers_and_unclear_reopens(topic: TopicDefinition) -> None:
    reducer = StateReducer()
    state = reducer.apply(
        topic,
        state_for(topic),
        EvaluationResult(
            covered=["consumer_group"],
            evidence=[evidence("consumer_group", Judgment.CORRECT, "group", 1)],
            confidence=1,
        ),
        "group",
    )
    assert "consumer_group" in state.covered_concepts

    state = reducer.apply(
        topic,
        state,
        EvaluationResult(
            unclear=["consumer_group"],
            evidence=[evidence("consumer_group", Judgment.UNCLEAR, "maybe", 2)],
            confidence=1,
        ),
        "maybe",
    )
    assert "consumer_group" not in state.covered_concepts
    assert "consumer_group" in state.unclear_concepts
    assert "consumer_group" in missing_concepts(topic, state)


def test_misconception_reopens_then_explicit_resolution_clears_it(
    topic: TopicDefinition,
) -> None:
    reducer = StateReducer()
    initial = state_for(topic).model_copy(update={"covered_concepts": frozenset({"offset"})})
    detected = reducer.apply(
        topic,
        initial,
        EvaluationResult(
            misconceptions=["M02"],
            evidence=[evidence("offset", Judgment.INCORRECT, "wrong", 1)],
            confidence=1,
        ),
        "wrong",
    )
    assert "offset" not in detected.covered_concepts
    assert detected.active_misconceptions == frozenset({"M02"})

    resolved = reducer.apply(
        topic,
        detected,
        EvaluationResult(
            covered=["offset"],
            resolved_misconceptions=["M02"],
            evidence=[evidence("offset", Judgment.CORRECT, "right", 2)],
            confidence=1,
        ),
        "right",
    )
    assert "offset" in resolved.covered_concepts
    assert not resolved.active_misconceptions


def test_rejects_unknown_ids_and_quotes_not_in_message(topic: TopicDefinition) -> None:
    reducer = StateReducer()
    with pytest.raises(InvalidEvaluationError, match="unknown IDs"):
        reducer.apply(
            topic,
            state_for(topic),
            EvaluationResult(
                covered=["invented"],
                evidence=[evidence("invented", Judgment.CORRECT, "claim", 1)],
                confidence=1,
            ),
            "claim",
        )

    with pytest.raises(InvalidEvaluationError, match="quote"):
        reducer.apply(
            topic,
            state_for(topic),
            EvaluationResult(
                covered=["offset"],
                evidence=[evidence("offset", Judgment.CORRECT, "not present", 1)],
                confidence=1,
            ),
            "different text",
        )
