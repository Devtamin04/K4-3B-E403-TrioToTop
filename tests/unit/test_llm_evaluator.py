from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.adapters.evaluator_llm import (
    EvaluationOutputValidator,
    EvaluatorEvidencePayload,
    EvaluatorOutputPayload,
    LlmEvaluator,
    find_exact_normalized_span,
)
from app.llm.errors import (
    LlmInvalidOutputError,
    LlmPermanentError,
    LlmRefusalError,
    LlmTransientError,
)
from app.teachback.exceptions import EvaluationFailedError, InvalidEvaluationError
from app.teachback.models import Judgment, TeachBackState, TopicDefinition
from tests.helpers import ScriptedStructuredLlmClient

ROOT = Path(__file__).resolve().parents[2]
PROMPT = ROOT / "app" / "prompts" / "evaluator_v1.md"


def make_state(topic: TopicDefinition, **updates: object) -> TeachBackState:
    state = TeachBackState(session_id="session", topic_id=topic.id, topic_version=topic.version)
    return state.model_copy(update=updates)


def correct_offset_payload(quote: str = "vị trí record") -> EvaluatorOutputPayload:
    return EvaluatorOutputPayload(
        covered=["offset"],
        evidence=[
            EvaluatorEvidencePayload(
                concept_id="offset",
                user_quote=quote,
                judgment=Judgment.CORRECT,
                explanation="Offset is a record position.",
                confidence=0.99,
            )
        ],
        confidence=0.99,
    )


def test_valid_result_uses_pinned_topic_and_does_not_mutate_state(
    topic: TopicDefinition,
) -> None:
    client = ScriptedStructuredLlmClient([correct_offset_payload()])
    evaluator = LlmEvaluator(
        client=client,
        model="configured-model",
        prompt_path=PROMPT,
    )
    state = make_state(topic, turn_count=4)
    before = state.model_dump_json()

    result = evaluator.evaluate(topic, state, (), "Offset là vị trí record trong partition.")

    assert result.covered == ["offset"]
    assert result.evidence[0].turn == 5
    assert state.model_dump_json() == before
    request = json.loads(client.calls[0]["user_input"])
    assert request["topic"]["id"] == topic.id
    assert request["topic"]["version"] == topic.version
    assert client.calls[0]["model"] == "configured-model"
    assert "choose an action" in client.calls[0]["system_prompt"]


def test_unicode_and_whitespace_normalization_returns_exact_source_span() -> None:
    source = "Offset la\u0300   vi\u0323 tri\u0301\nrecord trong partition."
    candidate = "là vị trí record"

    resolved = find_exact_normalized_span(source, candidate)

    assert resolved is not None
    assert resolved in source
    assert resolved != candidate


def test_paraphrased_or_invented_quote_is_rejected(topic: TopicDefinition) -> None:
    validator = EvaluationOutputValidator()
    with pytest.raises(InvalidEvaluationError, match="originate"):
        validator.validate(
            topic=topic,
            state=make_state(topic),
            payload=correct_offset_payload("record position"),
            latest_user_message="Offset là vị trí record trong partition.",
        )


def test_unknown_id_is_retried_then_rejected_before_reducer(topic: TopicDefinition) -> None:
    invalid = EvaluatorOutputPayload(
        covered=["invented"],
        evidence=[
            EvaluatorEvidencePayload(
                concept_id="invented",
                user_quote="claim",
                judgment=Judgment.CORRECT,
                explanation="Invented concept.",
                confidence=1,
            )
        ],
        confidence=1,
    )
    client = ScriptedStructuredLlmClient([invalid, invalid])
    evaluator = LlmEvaluator(
        client=client,
        model="configured-model",
        prompt_path=PROMPT,
        max_attempts=2,
    )

    with pytest.raises(EvaluationFailedError, match="2 attempts"):
        evaluator.evaluate(topic, make_state(topic), (), "claim")
    assert len(client.calls) == 2
    assert "VALIDATION_FEEDBACK_FROM_PREVIOUS_ATTEMPT" in client.calls[1]["user_input"]


def test_transient_and_invalid_output_failures_retry_then_succeed(
    topic: TopicDefinition,
) -> None:
    for error in (LlmTransientError("timeout"), LlmInvalidOutputError("bad schema")):
        client = ScriptedStructuredLlmClient([error, correct_offset_payload()])
        evaluator = LlmEvaluator(
            client=client,
            model="configured-model",
            prompt_path=PROMPT,
            max_attempts=2,
        )
        result = evaluator.evaluate(
            topic, make_state(topic), (), "Offset là vị trí record trong partition."
        )
        assert result.covered == ["offset"]
        assert len(client.calls) == 2
        if isinstance(error, LlmInvalidOutputError):
            assert "VALIDATION_FEEDBACK_FROM_PREVIOUS_ATTEMPT" in client.calls[1]["user_input"]


@pytest.mark.parametrize(
    "error",
    [LlmPermanentError("auth"), LlmRefusalError("refused")],
)
def test_permanent_error_and_refusal_do_not_retry(topic: TopicDefinition, error: Exception) -> None:
    client = ScriptedStructuredLlmClient([error, correct_offset_payload()])
    evaluator = LlmEvaluator(
        client=client,
        model="configured-model",
        prompt_path=PROMPT,
        max_attempts=2,
    )

    with pytest.raises(EvaluationFailedError):
        evaluator.evaluate(topic, make_state(topic), (), "Offset là vị trí record.")
    assert len(client.calls) == 1


def test_resolution_requires_active_misconception(topic: TopicDefinition) -> None:
    payload = correct_offset_payload()
    payload = payload.model_copy(update={"resolved_misconceptions": ["M02"]})

    with pytest.raises(InvalidEvaluationError, match="not active"):
        EvaluationOutputValidator().validate(
            topic=topic,
            state=make_state(topic),
            payload=payload,
            latest_user_message="Offset là vị trí record.",
        )


def test_output_schema_forbids_policy_or_response_fields() -> None:
    with pytest.raises(ValueError):
        EvaluatorOutputPayload.model_validate(
            {
                "covered": [],
                "unclear": [],
                "misconceptions": [],
                "resolved_misconceptions": [],
                "evidence": [],
                "recommended_target": None,
                "confidence": 1,
                "action": "FINISH",
                "response": "You understand everything.",
            }
        )
