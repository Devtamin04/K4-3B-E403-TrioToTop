from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pytest

from app.adapters.evaluator_llm import (
    EvaluationOutputValidator,
    EvaluatorEvidencePayload,
    EvaluatorOutputPayload,
)
from app.adapters.topics_yaml import YamlTopicRepository
from app.teachback.exceptions import InvalidEvaluationError
from app.teachback.models import (
    ConceptElement,
    CoveragePolicy,
    EvaluationResult,
    Evidence,
    Judgment,
    Message,
    TeachBackState,
    TopicDefinition,
)
from eval_harness.models import load_dataset
from eval_harness.safety import calculate_safety_metrics, run_case_safety, safety_gate_passes

ROOT = Path(__file__).resolve().parents[2]


def _topic() -> TopicDefinition:
    return YamlTopicRepository(ROOT / "knowledge").get("kafka_consumer_group")


def _case_state(topic: TopicDefinition, covered: list[str]) -> TeachBackState:
    return TeachBackState(
        session_id="safety",
        topic_id=topic.id,
        topic_version=topic.version,
        covered_concepts=frozenset(covered),
    )


class StubEvaluator:
    """Returns scripted predictions so safety runs stay deterministic."""

    def __init__(self, results: Sequence[EvaluationResult | Exception]) -> None:
        self._results = list(results)

    def evaluate(
        self,
        topic: TopicDefinition,
        state: TeachBackState,
        history: Sequence[Message],
        latest_user_message: str,
    ) -> EvaluationResult:
        del topic, state, history, latest_user_message
        outcome = self._results.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _finishing_prediction(case_message: str) -> EvaluationResult:
    return EvaluationResult(
        covered=["group_id"],
        evidence=[
            Evidence(
                concept_id="group_id",
                user_quote=case_message,
                judgment=Judgment.CORRECT,
                explanation="Deliberately unsafe prediction.",
                confidence=1,
                turn=1,
            )
        ],
        confidence=1,
    )


def _safe_prediction() -> EvaluationResult:
    return EvaluationResult(confidence=0.5)


def test_single_unsafe_finish_among_many_runs_fails_the_gate() -> None:
    case = next(
        item
        for item in load_dataset(ROOT / "eval_harness" / "datasets" / "evaluator_dataset.yaml")
        if item.id == "ambiguous_group_id"
    )
    topic = _topic()
    predictions: list[EvaluationResult | Exception] = [_safe_prediction() for _ in range(4)]
    predictions.insert(2, _finishing_prediction(case.latest_user_message))

    result = run_case_safety(case=case, topic=topic, evaluator=StubEvaluator(predictions), runs=5)
    metrics = calculate_safety_metrics([result], runs=5)

    assert result.unsafe_finishes == 1
    assert result.verdict == "UNSAFE"
    assert metrics.unsafe_finish_count == 1
    assert metrics.per_case_worst_case["ambiguous_group_id"] == "UNSAFE"
    assert not safety_gate_passes(metrics)


def test_all_safe_runs_pass_the_gate() -> None:
    case = next(
        item
        for item in load_dataset(ROOT / "eval_harness" / "datasets" / "evaluator_dataset.yaml")
        if item.id == "ambiguous_group_id"
    )

    result = run_case_safety(
        case=case,
        topic=_topic(),
        evaluator=StubEvaluator([_safe_prediction() for _ in range(5)]),
        runs=5,
    )
    metrics = calculate_safety_metrics([result], runs=5)

    assert metrics.unsafe_finish_count == 0
    assert metrics.unsafe_finish_rate == 0
    assert metrics.per_case_worst_case["ambiguous_group_id"] == "SAFE"
    assert safety_gate_passes(metrics)


def test_evaluation_errors_are_not_counted_as_unsafe() -> None:
    case = next(
        item
        for item in load_dataset(ROOT / "eval_harness" / "datasets" / "evaluator_dataset.yaml")
        if item.id == "ambiguous_group_id"
    )

    result = run_case_safety(
        case=case,
        topic=_topic(),
        evaluator=StubEvaluator([RuntimeError("boom") for _ in range(3)]),
        runs=3,
    )

    assert result.errors == 3
    assert result.unsafe_finishes == 0
    assert result.verdict == "SAFE"


def test_safety_case_must_be_unsafe_by_definition() -> None:
    case = next(
        item
        for item in load_dataset(ROOT / "eval_harness" / "datasets" / "evaluator_dataset.yaml")
        if item.completion_safe
    )

    with pytest.raises(ValueError, match="completion_safe"):
        run_case_safety(case=case, topic=_topic(), evaluator=StubEvaluator([]), runs=1)


# --- validator rules -------------------------------------------------------


def _payload(**evidence_fields: object) -> EvaluatorOutputPayload:
    base = {
        "concept_id": "group_id",
        "user_quote": "Kafka biết chúng liên quan với nhau",
        "judgment": Judgment.CORRECT,
        "explanation": "Reflects the shared group.id mechanism.",
        "confidence": 0.85,
    }
    base.update(evidence_fields)
    return EvaluatorOutputPayload(
        covered=["group_id"],
        evidence=[EvaluatorEvidencePayload.model_validate(base)],
        confidence=0.85,
    )


MESSAGE = "Các consumer ở cùng nhóm vì Kafka biết chúng liên quan với nhau."


def test_the_observed_unsafe_prediction_is_rejected() -> None:
    """Pins the run-2 payload that produced a real false completion."""

    topic = _topic().model_copy()
    concept = topic.concept("group_id").model_copy(
        update={
            "required_elements": [
                ConceptElement(id="identifier_mechanism", description="names the shared identifier")
            ]
        }
    )
    topic = topic.model_copy(
        update={"concepts": [concept if c.id == "group_id" else c for c in topic.concepts]}
    )

    with pytest.raises(InvalidEvaluationError, match="demonstration requirement"):
        EvaluationOutputValidator().validate(
            topic=topic,
            state=_case_state(
                topic, ["consumer_group", "partition_assignment", "offset", "rebalance"]
            ),
            payload=_payload(),
            latest_user_message=MESSAGE,
        )


def test_inference_used_blocks_coverage() -> None:
    topic = _topic()

    with pytest.raises(InvalidEvaluationError, match="inferred understanding"):
        EvaluationOutputValidator().validate(
            topic=topic,
            state=_case_state(topic, []),
            payload=_payload(inference_used=True),
            latest_user_message=MESSAGE,
        )


def test_unknown_element_is_rejected() -> None:
    topic = _topic()

    with pytest.raises(InvalidEvaluationError, match="unknown elements"):
        EvaluationOutputValidator().validate(
            topic=topic,
            state=_case_state(topic, []),
            payload=_payload(demonstrated_elements=["nonexistent"]),
            latest_user_message=MESSAGE,
        )


def test_re_emitting_prior_coverage_is_rejected() -> None:
    topic = _topic()

    with pytest.raises(InvalidEvaluationError, match="strictly per turn"):
        EvaluationOutputValidator().validate(
            topic=topic,
            state=_case_state(topic, ["group_id"]),
            payload=_payload(),
            latest_user_message=MESSAGE,
        )


def test_concept_without_elements_remains_valid() -> None:
    topic = _topic()

    result = EvaluationOutputValidator().validate(
        topic=topic,
        state=_case_state(topic, []),
        payload=_payload(),
        latest_user_message=MESSAGE,
    )

    assert result.covered == ["group_id"]


def test_any_element_policy_accepts_one_element() -> None:
    elements = [
        ConceptElement(id="first", description="first element"),
        ConceptElement(id="second", description="second element"),
    ]
    concept = _topic().concept("group_id")
    all_required = concept.model_copy(update={"required_elements": elements})
    any_required = concept.model_copy(
        update={"required_elements": elements, "coverage_policy": CoveragePolicy.ANY_ELEMENT}
    )

    assert not all_required.elements_satisfy_policy(frozenset({"first"}))
    assert all_required.elements_satisfy_policy(frozenset({"first", "second"}))
    assert any_required.elements_satisfy_policy(frozenset({"first"}))
    assert not any_required.elements_satisfy_policy(frozenset())
