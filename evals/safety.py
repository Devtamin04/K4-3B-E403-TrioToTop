from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass, field

from app.teachback.interfaces import Evaluator
from app.teachback.models import Action, EvaluationResult, TopicDefinition
from app.teachback.policy import PolicyEngine
from app.teachback.state import StateReducer
from evals.models import RegressionCase


@dataclass(frozen=True, slots=True)
class CaseSafetyResult:
    """Worst-case safety verdict for one case across repeated runs."""

    case_id: str
    category: str
    runs: int
    unsafe_finishes: int
    errors: int

    @property
    def verdict(self) -> str:
        return "UNSAFE" if self.unsafe_finishes else "SAFE"


@dataclass(frozen=True, slots=True)
class SafetyMetrics:
    """Repeated-run safety metrics, kept apart from precision/recall."""

    unsafe_finish_count: int
    unsafe_finish_rate: float
    safety_runs: int
    unsafe_cases: int
    evaluation_errors: int
    per_case_worst_case: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def calculate_safety_metrics(results: list[CaseSafetyResult], *, runs: int) -> SafetyMetrics:
    total_runs = sum(item.runs for item in results)
    unsafe = sum(item.unsafe_finishes for item in results)
    return SafetyMetrics(
        unsafe_finish_count=unsafe,
        unsafe_finish_rate=unsafe / total_runs if total_runs else 0.0,
        safety_runs=runs,
        unsafe_cases=len(results),
        evaluation_errors=sum(item.errors for item in results),
        per_case_worst_case={item.case_id: item.verdict for item in results},
    )


def safety_gate_passes(metrics: SafetyMetrics) -> bool:
    """A single unsafe FINISH anywhere fails the suite."""

    return metrics.unsafe_finish_count == 0


def run_case_safety(
    *,
    case: RegressionCase,
    topic: TopicDefinition,
    evaluator: Evaluator,
    runs: int,
    on_unsafe: Callable[[RegressionCase, EvaluationResult], None] | None = None,
) -> CaseSafetyResult:
    """Repeatedly evaluate one unsafe case through the real reducer and policy."""

    if runs < 1:
        raise ValueError("safety runs must be at least 1")
    if case.completion_safe:
        raise ValueError(f"case {case.id} is completion_safe and is not a safety case")

    reducer = StateReducer()
    policy = PolicyEngine()
    state = case.make_state(topic)
    history = case.make_history()
    unsafe = 0
    errors = 0

    for _ in range(runs):
        try:
            prediction = evaluator.evaluate(topic, state, history, case.latest_user_message)
            reduced = reducer.apply(topic, state, prediction, case.latest_user_message)
            decision = policy.choose(topic, reduced)
        except Exception:
            # A refused or invalid evaluation never reaches the learner and
            # cannot complete a session, so it is not an unsafe finish.
            errors += 1
            continue
        if decision.action is Action.FINISH:
            unsafe += 1
            if on_unsafe is not None:
                on_unsafe(case, prediction)

    return CaseSafetyResult(
        case_id=case.id,
        category=case.category,
        runs=runs,
        unsafe_finishes=unsafe,
        errors=errors,
    )
