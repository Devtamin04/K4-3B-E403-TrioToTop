from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.adapters.evaluator_llm import EvaluationOutputValidator
from app.adapters.student_fake import DeterministicStudentGenerator
from app.adapters.student_llm import LlmStudentGenerator
from app.adapters.topics_yaml import YamlTopicRepository
from app.composition import PROJECT_ROOT, build_evaluator, build_llm_client, build_student
from app.config import ConfigurationError, EvaluatorSettings, StudentSettings
from app.teachback.interfaces import StudentGenerator
from app.teachback.models import EvaluationResult, TopicDefinition
from eval_harness.golden import build_report, load_golden_set, run_case, write_run_artifacts
from eval_harness.metrics import calculate_metrics, provisional_gates_pass
from eval_harness.models import RegressionCase, load_dataset
from eval_harness.safety import calculate_safety_metrics, run_case_safety, safety_gate_passes
from eval_harness.student_judge import AdversarialJudgement, StudentJudgement, StudentResponseJudge
from eval_harness.student_metrics import (
    StudentCaseOutcome,
    calculate_student_metrics,
    evaluate_hidden_state_leak,
    student_gates_pass,
)
from eval_harness.student_models import CaseType, StudentCase, load_student_dataset

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    parser = argparse.ArgumentParser(description="Run hidden-evaluator regressions")
    parser.add_argument("--mode", choices=("offline", "live"), default="offline")
    parser.add_argument("--target", choices=("evaluator", "student", "golden"), default="evaluator")
    parser.add_argument(
        "--safety-runs",
        type=int,
        default=0,
        help="repeat every completion_safe=false case N times and run the safety gate",
    )
    arguments = parser.parse_args()

    if arguments.safety_runs:
        return _run_safety(live=arguments.mode == "live", runs=arguments.safety_runs)
    if arguments.target == "golden":
        return _run_golden(live=arguments.mode == "live")
    if arguments.target == "student":
        return _run_student(live=arguments.mode == "live")
    return _run_evaluator(live=arguments.mode == "live")


GOLDEN_PASS_TARGET = 0.80
"""Quality bar chốt trước lượt đo đầu; không đổi sau khi thấy kết quả."""


def _run_golden(*, live: bool) -> int:
    cases = load_golden_set(ROOT / "eval_harness" / "datasets" / "golden_set.yaml")
    topic = YamlTopicRepository(ROOT / "knowledge").get("context_window")

    if not live:
        print("SKIPPED: bộ golden set cần --mode live để chạy qua evaluator thật")
        return 0
    try:
        evaluator_settings = EvaluatorSettings.from_env()
        student_settings = StudentSettings.from_env()
    except ConfigurationError as error:
        print(f"SKIPPED: chưa cấu hình evaluator: {error}")
        return 0
    if evaluator_settings.backend == "fixture":
        print("SKIPPED: cần LLM_PROVIDER thật, không dùng fixture")
        return 0

    evaluator = build_evaluator(evaluator_settings)
    student = build_student(student_settings, evaluator_settings)

    outcomes = [
        run_case(case=case, topic=topic, evaluator=evaluator, student=student) for case in cases
    ]
    report = build_report(outcomes)

    print(f"{'case':<32} {'loại':<8} {'action':<10} {'target':<16} kết quả")
    print("-" * 92)
    for item in report.outcomes:
        verdict = "ĐẠT" if item.passed else "KHÔNG ĐẠT"
        print(
            f"{item.case_id:<32} {item.category:<8} {item.action:<10} "
            f"{str(item.target or '-'):<16} {verdict}"
        )
        for reason in item.failures:
            print(f"    ↳ {reason}")

    print()
    print("  Theo lớp chỗ khó (guide §2.5):")
    for layer, (passed, total) in sorted(report.by_layer().items()):
        print(f"    lớp {layer}   {passed}/{total}")
    print("  Theo nhóm:")
    for category, (passed, total) in sorted(report.by_category().items()):
        print(f"    {category:<16} {passed}/{total}")

    predicted = [item for item in report.outcomes if item.predicted_fail]
    held = sum(1 for item in predicted if item.prediction_held)
    print(f"\n  Case dự đoán trượt: {len(predicted)}, đoán đúng {held}/{len(predicted)}")

    table, trace = write_run_artifacts(
        report,
        directory=ROOT / "logs" / "runs",
        trace_directory=ROOT / "logs" / "traces",
        model=evaluator_settings.model or "?",
        prompt_version=evaluator_settings.prompt_version,
        quality_bar=GOLDEN_PASS_TARGET,
    )
    print(f"\nTỔNG: {report.passed}/{report.total} case ĐẠT = {report.pass_rate:.1%}")
    print("QUALITY BAR:", f"{GOLDEN_PASS_TARGET:.0%}")
    print("GOLDEN_GATE:", "PASS" if report.pass_rate >= GOLDEN_PASS_TARGET else "FAIL")
    print(f"Đã ghi: {table.relative_to(ROOT)} · {trace.relative_to(ROOT)}")
    return 0 if report.pass_rate >= GOLDEN_PASS_TARGET else 1


def _run_safety(*, live: bool, runs: int) -> int:
    cases = [
        case
        for case in load_dataset(ROOT / "eval_harness" / "datasets" / "evaluator_dataset.yaml")
        if not case.completion_safe
    ]
    topic_repository = YamlTopicRepository(ROOT / "knowledge")
    topics = {case.topic_id: topic_repository.get(case.topic_id) for case in cases}

    if not live:
        print("SKIPPED: the safety regression requires --mode live")
        return 0
    try:
        settings = EvaluatorSettings.from_env()
    except ConfigurationError as error:
        print(f"SKIPPED: live evaluator is not configured: {error}")
        return 0
    if settings.backend == "fixture":
        print("SKIPPED: the safety regression requires LLM_PROVIDER, not fixture mode")
        return 0

    evaluator = build_evaluator(settings)

    def report_unsafe(case: RegressionCase, prediction: EvaluationResult) -> None:
        print(f"UNSAFE FINISH {case.id}: covered={sorted(prediction.covered)}")
        for item in prediction.evidence:
            print(
                f"  evidence concept={item.concept_id} judgment={item.judgment.value} "
                f"inference_used={item.inference_used} "
                f"demonstrated={sorted(item.demonstrated_elements)}"
            )
            print(f"    quote: {item.user_quote!r}")

    results = [
        run_case_safety(
            case=case,
            topic=topics[case.topic_id],
            evaluator=evaluator,
            runs=runs,
            on_unsafe=report_unsafe,
        )
        for case in cases
    ]
    metrics = calculate_safety_metrics(results, runs=runs)
    print(json.dumps(metrics.as_dict(), indent=2, sort_keys=True))
    print("prompt_version:", settings.prompt_version)
    print("SAFETY_GATE:", "PASS" if safety_gate_passes(metrics) else "FAIL")
    return 0 if safety_gate_passes(metrics) else 1


def _run_evaluator(*, live: bool) -> int:
    cases = load_dataset(ROOT / "eval_harness" / "datasets" / "evaluator_dataset.yaml")
    topic_repository = YamlTopicRepository(ROOT / "knowledge")
    topics = {case.topic_id: topic_repository.get(case.topic_id) for case in cases}

    if live:
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


def _run_student(*, live: bool) -> int:
    cases = load_student_dataset(ROOT / "eval_harness" / "datasets" / "student_dataset.yaml")
    topic_repository = YamlTopicRepository(ROOT / "knowledge")
    topics = {case.topic_id: topic_repository.get(case.topic_id) for case in cases}

    student: StudentGenerator = DeterministicStudentGenerator()
    judge: StudentResponseJudge | None = None

    if live:
        try:
            evaluator_settings = EvaluatorSettings.from_env()
            student_settings = StudentSettings.from_env()
        except ConfigurationError as error:
            print(f"SKIPPED: live student is not configured: {error}")
            return 0
        if evaluator_settings.backend == "fixture":
            print("SKIPPED: live student regression requires LLM_PROVIDER, not fixture mode")
            return 0
        if student_settings.backend != "llm" or student_settings.model is None:
            print("SKIPPED: live student regression requires STUDENT_BACKEND=llm and STUDENT_MODEL")
            return 0
        client = build_llm_client(evaluator_settings)
        student = LlmStudentGenerator(
            client=client,
            model=student_settings.model,
            prompt_path=PROJECT_ROOT / "app" / "prompts" / "student_v1.md",
            max_attempts=student_settings.max_attempts,
            timeout_seconds=student_settings.timeout_seconds,
        )
        judge = StudentResponseJudge(
            client=client,
            model=student_settings.model,
            timeout_seconds=student_settings.timeout_seconds,
        )

    outcomes = [_run_student_case(case, topics[case.topic_id], student, judge) for case in cases]
    metrics = calculate_student_metrics(outcomes)
    print(json.dumps(metrics.as_dict(), indent=2, sort_keys=True))
    for outcome in outcomes:
        if outcome.failures:
            print(
                f"FAILED {outcome.case_id} [{outcome.case_type.value}/{outcome.category}]: "
                f"{', '.join(outcome.failures)}"
            )
            print(f"  response: {outcome.response}")
    print("STUDENT_GATES:", "PASS" if student_gates_pass(metrics) else "FAIL")
    return 0 if student_gates_pass(metrics) else 1


def _run_student_case(
    case: StudentCase,
    topic: TopicDefinition,
    student: StudentGenerator,
    judge: StudentResponseJudge | None,
) -> StudentCaseOutcome:
    decision = case.make_decision()
    curated = case.curated_question(topic)
    response = student.generate(topic, case.make_state(topic), decision, case.make_history())
    adversarial = case.case_type is CaseType.ADVERSARIAL

    judgement: StudentJudgement | AdversarialJudgement
    if judge is None:
        judgement = _offline_judgement(response, adversarial=adversarial)
    elif adversarial:
        judgement = judge.judge_adversarial(
            action=case.action.value,
            curated_question=curated,
            latest_human_message=case.latest_user_message,
            expected_answer=case.expected_answer(topic),
            response=response,
        )
    else:
        judgement = judge.judge(
            action=case.action.value,
            curated_question=curated,
            latest_human_message=case.latest_user_message,
            expected_answer=case.expected_answer(topic),
            response=response,
        )

    return StudentCaseOutcome(
        case_id=case.id,
        category=case.category,
        case_type=case.case_type,
        action=case.action.value,
        response=response,
        judgement=judgement,
        hidden_state_leak=evaluate_hidden_state_leak(topic=topic, case=case, response=response),
        question_mark_violation=response.count("?") > 1,
        used_fallback=response == curated,
    )


def _offline_judgement(
    response: str, *, adversarial: bool
) -> StudentJudgement | AdversarialJudgement:
    """Offline mode exercises the harness against the curated questions.

    The curated questions are the deterministic baseline the student falls back
    to, so they are treated as adherent by construction. Only the deterministic
    checks are meaningful without a judge model.
    """

    question_count = min(response.count("?"), 1)
    if adversarial:
        return AdversarialJudgement(
            resists_manipulation=True,
            withholds_internal_information=True,
            preserves_student_role=True,
            returns_to_instructed_task=True,
            performs_instructed_action=True,
            addresses_instructed_focus=True,
            reveals_answer=False,
            stays_in_student_role=True,
            main_question_count=question_count,
        )
    return StudentJudgement(
        performs_instructed_action=True,
        addresses_instructed_focus=True,
        reveals_answer=False,
        stays_in_student_role=True,
        main_question_count=question_count,
        is_relevant=True,
    )


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
