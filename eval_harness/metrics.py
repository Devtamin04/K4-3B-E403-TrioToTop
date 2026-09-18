from __future__ import annotations

from dataclasses import asdict, dataclass

from app.teachback.models import Action, EvaluationResult, TopicDefinition
from app.teachback.policy import PolicyEngine
from app.teachback.state import StateReducer
from eval_harness.models import RegressionCase


@dataclass(frozen=True, slots=True)
class RegressionMetrics:
    concept_precision: float
    concept_recall: float
    misconception_precision: float
    misconception_recall: float
    false_positive_concept_coverage: float
    false_completion_risk: float
    resolution_accuracy: float
    cases: int

    def as_dict(self) -> dict[str, float | int]:
        return asdict(self)


def calculate_metrics(
    cases: list[RegressionCase],
    predictions: list[EvaluationResult],
    topics: dict[str, TopicDefinition],
) -> RegressionMetrics:
    if len(cases) != len(predictions):
        raise ValueError("cases and predictions must have equal length")

    concept_tp = concept_fp = concept_fn = 0
    misconception_tp = misconception_fp = misconception_fn = 0
    resolution_correct = 0
    unsafe_cases = false_completions = 0
    reducer = StateReducer()
    policy = PolicyEngine()

    for case, prediction in zip(cases, predictions, strict=True):
        expected_covered = set(case.expected.covered)
        predicted_covered = set(prediction.covered)
        concept_tp += len(expected_covered & predicted_covered)
        concept_fp += len(predicted_covered - expected_covered)
        concept_fn += len(expected_covered - predicted_covered)

        expected_misconceptions = set(case.expected.misconceptions)
        predicted_misconceptions = set(prediction.misconceptions)
        misconception_tp += len(expected_misconceptions & predicted_misconceptions)
        misconception_fp += len(predicted_misconceptions - expected_misconceptions)
        misconception_fn += len(expected_misconceptions - predicted_misconceptions)
        if set(prediction.resolved_misconceptions) == set(case.expected.resolved_misconceptions):
            resolution_correct += 1

        if not case.completion_safe:
            unsafe_cases += 1
            topic = topics[case.topic_id]
            state = case.make_state(topic)
            reduced = reducer.apply(topic, state, prediction, case.latest_user_message)
            if policy.choose(topic, reduced).action is Action.FINISH:
                false_completions += 1

    return RegressionMetrics(
        concept_precision=_ratio(concept_tp, concept_tp + concept_fp),
        concept_recall=_ratio(concept_tp, concept_tp + concept_fn),
        misconception_precision=_ratio(misconception_tp, misconception_tp + misconception_fp),
        misconception_recall=_ratio(misconception_tp, misconception_tp + misconception_fn),
        false_positive_concept_coverage=_ratio(concept_fp, concept_tp + concept_fp, empty_value=0),
        false_completion_risk=_ratio(false_completions, unsafe_cases, empty_value=0),
        resolution_accuracy=_ratio(resolution_correct, len(cases)),
        cases=len(cases),
    )


def provisional_gates_pass(metrics: RegressionMetrics) -> bool:
    return (
        metrics.concept_precision >= 0.85
        and metrics.concept_recall >= 0.85
        and metrics.misconception_precision >= 0.90
        and metrics.misconception_recall >= 0.90
        and metrics.false_positive_concept_coverage <= 0.05
        and metrics.false_completion_risk == 0
    )


def _ratio(numerator: int, denominator: int, *, empty_value: float = 1) -> float:
    if denominator == 0:
        return empty_value
    return numerator / denominator
