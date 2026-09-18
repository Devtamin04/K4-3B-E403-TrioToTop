from __future__ import annotations

from pathlib import Path

from app.adapters.evaluator_llm import EvaluationOutputValidator
from app.adapters.topics_yaml import YamlTopicRepository
from app.teachback.models import EvaluationResult, Evidence, Judgment
from evals.metrics import calculate_metrics, provisional_gates_pass
from evals.models import load_dataset

ROOT = Path(__file__).resolve().parents[2]


def test_dataset_covers_required_categories_and_gold_predictions_pass() -> None:
    cases = load_dataset(ROOT / "evals" / "dataset.yaml")
    topics = YamlTopicRepository(ROOT / "knowledge")
    topic_map = {case.topic_id: topics.get(case.topic_id) for case in cases}
    required_categories = {
        "fully_correct_explanation",
        "partial_explanation",
        "missing_concept",
        "ambiguous_explanation",
        "known_misconception",
        "misconception_self_correction",
        "conflicting_statements",
        "off_topic_answer",
        "very_short_answer",
        "user_asks_ai_for_answer",
    }
    assert required_categories <= {case.category for case in cases}

    validator = EvaluationOutputValidator()
    predictions = [
        validator.validate(
            topic=topic_map[case.topic_id],
            state=case.make_state(topic_map[case.topic_id]),
            payload=case.expected,
            latest_user_message=case.latest_user_message,
        )
        for case in cases
    ]
    metrics = calculate_metrics(cases, predictions, topic_map)

    assert metrics.concept_precision == 1
    assert metrics.concept_recall == 1
    assert metrics.misconception_precision == 1
    assert metrics.misconception_recall == 1
    assert metrics.false_positive_concept_coverage == 0
    assert metrics.false_completion_risk == 0
    assert provisional_gates_pass(metrics)


def test_false_completion_metric_detects_unsafe_finish() -> None:
    all_cases = load_dataset(ROOT / "evals" / "dataset.yaml")
    case = next(item for item in all_cases if item.id == "ambiguous_group_id")
    topic = YamlTopicRepository(ROOT / "knowledge").get(case.topic_id)
    prediction = EvaluationResult(
        covered=["group_id"],
        evidence=[
            Evidence(
                concept_id="group_id",
                user_quote=case.latest_user_message,
                judgment=Judgment.CORRECT,
                explanation="Deliberately unsafe test prediction.",
                confidence=1,
                turn=1,
            )
        ],
        confidence=1,
    )

    metrics = calculate_metrics([case], [prediction], {topic.id: topic})

    assert metrics.false_completion_risk == 1
    assert not provisional_gates_pass(metrics)
