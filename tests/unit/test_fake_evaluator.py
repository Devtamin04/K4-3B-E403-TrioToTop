from pathlib import Path

import pytest

from app.adapters.evaluator_fake import FixtureEvaluator
from app.teachback.models import TeachBackState, TopicDefinition

ROOT = Path(__file__).resolve().parents[2]


def test_fixture_evaluator_uses_exact_message_and_current_turn(topic: TopicDefinition) -> None:
    evaluator = FixtureEvaluator(ROOT / "tests" / "fixtures" / "evaluator_cases.yaml")
    state = TeachBackState(
        session_id="session",
        topic_id=topic.id,
        topic_version=topic.version,
        turn_count=3,
    )

    result = evaluator.evaluate(
        topic,
        state,
        (),
        "Offset là số message còn lại chưa đọc.",
    )

    assert result.misconceptions == ["M02"]
    assert result.evidence[0].turn == 4


def test_unknown_message_returns_logged_empty_observation(
    topic: TopicDefinition, caplog: pytest.LogCaptureFixture
) -> None:
    evaluator = FixtureEvaluator(ROOT / "tests" / "fixtures" / "evaluator_cases.yaml")
    state = TeachBackState(session_id="session", topic_id=topic.id, topic_version=topic.version)

    result = evaluator.evaluate(topic, state, (), "An arbitrary message")

    assert result.evidence == []
    assert result.confidence == 0
    assert "returning empty observation" in caplog.text
