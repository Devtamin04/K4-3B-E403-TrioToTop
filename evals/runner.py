from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.adapters.evaluator_llm import EvaluationOutputValidator
from app.adapters.topics_yaml import YamlTopicRepository
from app.composition import build_evaluator
from app.config import ConfigurationError, EvaluatorSettings
from app.teachback.models import EvaluationResult, TopicDefinition
from evals.metrics import calculate_metrics, provisional_gates_pass
from evals.models import RegressionCase, load_dataset

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    parser = argparse.ArgumentParser(description="Run hidden-evaluator regressions")
    parser.add_argument("--mode", choices=("offline", "live"), default="offline")
    arguments = parser.parse_args()

    cases = load_dataset(ROOT / "evals" / "dataset.yaml")
    topic_repository = YamlTopicRepository(ROOT / "knowledge")
    topics = {case.topic_id: topic_repository.get(case.topic_id) for case in cases}

    if arguments.mode == "live":
        try:
            settings = EvaluatorSettings.from_env()
        except ConfigurationError as error:
            print(f"SKIPPED: live evaluator is not configured: {error}")
            return 0
        if settings.backend == "fixture":
            print("SKIPPED: live regression requires LLM_PROVIDER, not fixture mode")
            return 0
        evaluator = build_evaluator(settings)
        predictions = [
            evaluator.evaluate(
                topics[case.topic_id],
                case.make_state(topics[case.topic_id]),
                case.make_history(),
                case.latest_user_message,
            )
            for case in cases
        ]
    else:
        predictions = _gold_predictions(cases, topics)

    metrics = calculate_metrics(cases, predictions, topics)
    print(json.dumps(metrics.as_dict(), indent=2, sort_keys=True))
    print("PROVISIONAL_GATES:", "PASS" if provisional_gates_pass(metrics) else "FAIL")
    return 0 if provisional_gates_pass(metrics) else 1


def _gold_predictions(
    cases: list[RegressionCase], topics: dict[str, TopicDefinition]
) -> list[EvaluationResult]:
    validator = EvaluationOutputValidator()
    return [
        validator.validate(
            topic=topics[case.topic_id],
            state=case.make_state(topics[case.topic_id]),
            payload=case.expected,
            latest_user_message=case.latest_user_message,
        )
        for case in cases
    ]


if __name__ == "__main__":
    raise SystemExit(main())
