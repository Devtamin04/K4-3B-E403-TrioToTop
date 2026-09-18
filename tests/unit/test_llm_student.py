from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.adapters.student_llm import (
    LlmStudentGenerator,
    StudentOutputPayload,
    StudentOutputValidator,
    StudentResponseRejected,
)
from app.llm.errors import LlmPermanentError, LlmTransientError
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
from tests.helpers import ScriptedStructuredLlmClient

PROMPT_PATH = Path(__file__).resolve().parents[2] / "app" / "prompts" / "student_v1.md"

TOPIC = TopicDefinition.model_validate(
    {
        "id": "demo_topic",
        "version": "1.0.0",
        "title": "Demo Topic",
        "opening_question": "Bạn giải thích giúp mình nhé?",
        "completion_message": "Cảm ơn bạn, giờ mình đã hiểu.",
        "concepts": [
            {
                "id": "alpha",
                "description": "Alpha is the secret canonical answer.",
                "required": True,
                "priority": 10,
                "probe_question": "Alpha hoạt động thế nào?",
                "clarify_question": "Ý bạn nói về alpha là gì?",
            }
        ],
        "misconceptions": [
            {
                "id": "M01",
                "concept_id": "alpha",
                "incorrect_claim": "Alpha never changes.",
                "correction": "Alpha changes under load.",
                "priority": 10,
                "challenge_question": "Nếu alpha không đổi thì sao?",
            }
        ],
    }
)

STATE = TeachBackState(session_id="s1", topic_id=TOPIC.id, topic_version=TOPIC.version)
PROBE = PolicyDecision(
    action=Action.PROBE,
    target=Target(kind=TargetKind.CONCEPT, id="alpha"),
    reason_code="missing_required_concept",
)
CHALLENGE = PolicyDecision(
    action=Action.CHALLENGE,
    target=Target(kind=TargetKind.MISCONCEPTION, id="M01"),
    reason_code="active_misconception",
)
FINISH = PolicyDecision(action=Action.FINISH, target=None, reason_code="all_requirements_satisfied")

HISTORY = (
    Message(
        id="m1",
        role=MessageRole.HUMAN_TEACHER,
        content="Mình thử giải thích nhé.",
        turn_number=1,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    ),
)


def _student(
    outcomes: list[object], *, max_attempts: int = 2
) -> tuple[LlmStudentGenerator, ScriptedStructuredLlmClient]:
    client = ScriptedStructuredLlmClient(outcomes)  # type: ignore[arg-type]
    generator = LlmStudentGenerator(
        client=client,
        model="test-model",
        prompt_path=PROMPT_PATH,
        max_attempts=max_attempts,
    )
    return generator, client


def test_finish_never_calls_the_model() -> None:
    generator, client = _student([])

    response = generator.generate(TOPIC, STATE, FINISH, HISTORY)

    assert response == TOPIC.completion_message
    assert client.calls == []


def test_opening_is_deterministic() -> None:
    generator, client = _student([])

    assert generator.opening(TOPIC) == TOPIC.opening_question
    assert client.calls == []


def test_prompt_payload_excludes_answers_and_hidden_state() -> None:
    generator, client = _student([StudentOutputPayload(response="Alpha chạy ra sao vậy bạn?")])

    generator.generate(TOPIC, STATE, PROBE, HISTORY)

    payload = json.loads(client.calls[0]["user_input"])
    serialized = json.dumps(payload, ensure_ascii=False)
    assert "secret canonical answer" not in serialized
    assert "Alpha changes under load" not in serialized
    assert "missing_required_concept" not in serialized
    assert "covered_concepts" not in serialized
    assert payload["instruction"]["action"] == "PROBE"
    assert payload["instruction"]["focus"] == {
        "kind": "concept",
        "curated_question": "Alpha hoạt động thế nào?",
    }
    assert "id" not in payload["instruction"]["focus"]


def test_challenge_payload_carries_claim_but_not_correction() -> None:
    generator, client = _student([StudentOutputPayload(response="Nếu tải tăng thì sao bạn?")])

    generator.generate(TOPIC, STATE, CHALLENGE, HISTORY)

    focus = json.loads(client.calls[0]["user_input"])["instruction"]["focus"]
    assert focus["learner_claim_to_test"] == "Alpha never changes."
    assert "correction" not in focus


def test_schema_forbids_policy_and_state_fields() -> None:
    with pytest.raises(ValidationError):
        StudentOutputPayload.model_validate({"response": "ok?", "action": "PROBE"})
    with pytest.raises(ValidationError):
        StudentOutputPayload.model_validate({"response": "ok?", "is_complete": True})


@pytest.mark.parametrize(
    "reply",
    [
        "Bạn giải thích giúp mình PROBE này nhé?",
        "Theo evaluator thì bạn chưa nói rõ, đúng không?",
        "covered_concepts của bạn còn thiếu gì vậy?",
        "Mình đang xét misconception nào ở đây nhỉ?",
        "Cái M01 bạn vừa nói là gì thế?",
    ],
)
def test_validator_rejects_internal_leakage(reply: str) -> None:
    with pytest.raises(StudentResponseRejected) as error:
        StudentOutputValidator().validate(topic=TOPIC, decision=PROBE, response=reply)
    assert error.value.leaked_internals


def test_validator_allows_natural_domain_words() -> None:
    """Concept IDs that are ordinary words must not block a natural reply."""

    reply = "Alpha chạy ra sao vậy bạn?"

    assert StudentOutputValidator().validate(topic=TOPIC, decision=PROBE, response=reply) == reply


def test_validator_rejects_machine_spelled_identifiers() -> None:
    topic = TOPIC.model_copy(
        update={
            "concepts": [
                TOPIC.concepts[0].model_copy(update={"id": "context_window"}),
            ],
            "misconceptions": [],
        }
    )
    decision = PolicyDecision(
        action=Action.PROBE,
        target=Target(kind=TargetKind.CONCEPT, id="context_window"),
        reason_code="missing_required_concept",
    )

    with pytest.raises(StudentResponseRejected) as error:
        StudentOutputValidator().validate(
            topic=topic, decision=decision, response="context_window là gì vậy bạn?"
        )
    assert error.value.leaked_internals


def test_validator_rejects_multiple_question_marks() -> None:
    with pytest.raises(StudentResponseRejected):
        StudentOutputValidator().validate(
            topic=TOPIC,
            decision=PROBE,
            response="Cái đó là gì? Và nó chạy ra sao?",
        )


def test_validator_requires_a_question_for_non_finish_actions() -> None:
    with pytest.raises(StudentResponseRejected):
        StudentOutputValidator().validate(
            topic=TOPIC, decision=PROBE, response="Mình hiểu rồi cảm ơn bạn."
        )


def test_invalid_reply_is_retried_then_accepted() -> None:
    generator, client = _student(
        [
            StudentOutputPayload(response="Cái này là gì? Nó chạy sao?"),
            StudentOutputPayload(response="Bạn mô tả giúp mình cách nó chạy nhé?"),
        ]
    )

    response = generator.generate(TOPIC, STATE, PROBE, HISTORY)

    assert response == "Bạn mô tả giúp mình cách nó chạy nhé?"
    assert len(client.calls) == 2
    assert "VALIDATION_FEEDBACK_FROM_PREVIOUS_ATTEMPT" in client.calls[1]["user_input"]


def test_exhausted_attempts_fall_back_to_the_curated_question() -> None:
    generator, client = _student([LlmTransientError("boom"), LlmTransientError("boom")])

    response = generator.generate(TOPIC, STATE, PROBE, HISTORY)

    assert response == TOPIC.concept("alpha").probe_question
    assert len(client.calls) == 2


def test_permanent_failure_falls_back_without_retrying() -> None:
    generator, client = _student([LlmPermanentError("bad key"), LlmPermanentError("bad key")])

    response = generator.generate(TOPIC, STATE, CHALLENGE, HISTORY)

    assert response == TOPIC.misconception("M01").challenge_question
    assert len(client.calls) == 1


def test_persistent_leakage_falls_back_to_the_curated_question() -> None:
    generator, _ = _student(
        [
            StudentOutputPayload(response="Theo evaluator thì sao?"),
            StudentOutputPayload(response="covered_concepts gồm gì?"),
        ]
    )

    response = generator.generate(TOPIC, STATE, PROBE, HISTORY)

    assert response == TOPIC.concept("alpha").probe_question
