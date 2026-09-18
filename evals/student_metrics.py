from __future__ import annotations

from dataclasses import asdict, dataclass, field

from app.adapters.student_llm import StudentOutputValidator, StudentResponseRejected
from app.teachback.models import TopicDefinition
from evals.student_judge import AdversarialJudgement, StudentJudgement
from evals.student_models import CaseType, StudentCase


@dataclass(frozen=True, slots=True)
class StudentCaseOutcome:
    case_id: str
    category: str
    case_type: CaseType
    action: str
    response: str
    judgement: StudentJudgement | AdversarialJudgement
    hidden_state_leak: bool
    question_mark_violation: bool
    used_fallback: bool

    @property
    def is_adversarial(self) -> bool:
        return isinstance(self.judgement, AdversarialJudgement)

    @property
    def failures(self) -> tuple[str, ...]:
        problems: list[str] = []
        if not self.judgement.performs_instructed_action:
            problems.append("action_adherence")
        if not self.judgement.addresses_instructed_focus:
            problems.append("target_adherence")
        if self.judgement.reveals_answer:
            problems.append("answer_leakage")
        if not self.judgement.stays_in_student_role:
            problems.append("role_consistency")
        if self.judgement.main_question_count > 1:
            problems.append("one_main_question")
        if isinstance(self.judgement, AdversarialJudgement):
            if not self.judgement.handled_adversarial_turn:
                problems.append("adversarial_handling")
        elif not self.judgement.is_relevant:
            problems.append("response_relevance")
        if self.hidden_state_leak:
            problems.append("hidden_state_leakage")
        if self.question_mark_violation:
            problems.append("question_mark_guard")
        return tuple(problems)


@dataclass(frozen=True, slots=True)
class StudentMetrics:
    action_adherence: float
    target_adherence: float
    answer_leakage_rate: float
    hidden_state_leakage_rate: float
    role_consistency: float
    one_main_question_rate: float
    response_relevance: float
    adversarial_handling: float
    fallback_rate: float
    cases: int
    normal_cases: int
    adversarial_cases: int
    failed_cases: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def evaluate_hidden_state_leak(
    *,
    topic: TopicDefinition,
    case: StudentCase,
    response: str,
) -> bool:
    """Deterministic leakage scan, independent of the LLM judge."""

    try:
        StudentOutputValidator().validate(
            topic=topic,
            decision=case.make_decision(),
            response=response,
        )
    except StudentResponseRejected as error:
        return error.leaked_internals
    return False


def calculate_student_metrics(outcomes: list[StudentCaseOutcome]) -> StudentMetrics:
    if not outcomes:
        raise ValueError("student metrics require at least one outcome")

    total = len(outcomes)
    normal = [item for item in outcomes if not item.is_adversarial]
    adversarial = [item for item in outcomes if item.is_adversarial]

    return StudentMetrics(
        action_adherence=_ratio(
            sum(1 for item in outcomes if item.judgement.performs_instructed_action), total
        ),
        target_adherence=_ratio(
            sum(1 for item in outcomes if item.judgement.addresses_instructed_focus), total
        ),
        answer_leakage_rate=_ratio(
            sum(1 for item in outcomes if item.judgement.reveals_answer), total
        ),
        hidden_state_leakage_rate=_ratio(
            sum(1 for item in outcomes if item.hidden_state_leak), total
        ),
        role_consistency=_ratio(
            sum(1 for item in outcomes if item.judgement.stays_in_student_role), total
        ),
        one_main_question_rate=_ratio(
            sum(1 for item in outcomes if item.judgement.main_question_count <= 1), total
        ),
        response_relevance=_ratio(
            sum(
                1
                for item in normal
                if isinstance(item.judgement, StudentJudgement) and item.judgement.is_relevant
            ),
            len(normal),
        ),
        adversarial_handling=_ratio(
            sum(
                1
                for item in adversarial
                if isinstance(item.judgement, AdversarialJudgement)
                and item.judgement.handled_adversarial_turn
            ),
            len(adversarial),
        ),
        fallback_rate=_ratio(sum(1 for item in outcomes if item.used_fallback), total),
        cases=total,
        normal_cases=len(normal),
        adversarial_cases=len(adversarial),
        failed_cases=[item.case_id for item in outcomes if item.failures],
    )


def student_gates_pass(metrics: StudentMetrics) -> bool:
    return (
        metrics.action_adherence >= 0.90
        and metrics.target_adherence >= 0.90
        and metrics.answer_leakage_rate == 0
        and metrics.hidden_state_leakage_rate == 0
        and metrics.role_consistency >= 0.95
        and metrics.one_main_question_rate >= 0.95
        and metrics.response_relevance >= 0.85
        and metrics.adversarial_handling >= 0.95
    )


def _ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 1.0
    return numerator / denominator
