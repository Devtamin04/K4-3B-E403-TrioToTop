from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.teachback.interfaces import Evaluator, StudentGenerator
from app.teachback.models import (
    Action,
    Message,
    MessageRole,
    TeachBackState,
    TopicDefinition,
)
from app.teachback.policy import PolicyEngine
from app.teachback.state import StateReducer


class GoldenCase(BaseModel):
    """Một câu thử kèm tiêu chí ĐẠT kiểm chứng được bằng máy."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    category: str = Field(min_length=1)
    message: str = Field(min_length=1)
    prior_covered: list[str] = Field(default_factory=list)
    expect_action: Action | None = None
    expect_target: str | None = None
    forbid_finish: bool = False
    reply_must_not_contain: list[str] = Field(default_factory=list)
    note: str = ""


@dataclass(frozen=True, slots=True)
class CaseOutcome:
    case_id: str
    category: str
    action: str
    target: str | None
    reply: str
    failures: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.failures


@dataclass(frozen=True, slots=True)
class GoldenReport:
    total: int
    passed: int
    outcomes: list[CaseOutcome] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total else 0.0

    def by_category(self) -> dict[str, tuple[int, int]]:
        table: dict[str, list[int]] = {}
        for outcome in self.outcomes:
            row = table.setdefault(outcome.category, [0, 0])
            row[1] += 1
            if outcome.passed:
                row[0] += 1
        return {key: (value[0], value[1]) for key, value in table.items()}


def load_golden_set(path: Path) -> list[GoldenCase]:
    try:
        raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
        cases = [GoldenCase.model_validate(item) for item in raw]
    except (OSError, TypeError, yaml.YAMLError, ValidationError) as error:
        raise ValueError(f"golden set không hợp lệ {path}: {error}") from error
    ids = [case.id for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("ID trong golden set phải là duy nhất")
    return cases


def run_case(
    *,
    case: GoldenCase,
    topic: TopicDefinition,
    evaluator: Evaluator,
    student: StudentGenerator,
) -> CaseOutcome:
    """Chạy một lượt dạy đầy đủ: evaluator -> reducer -> policy -> student."""

    state = TeachBackState(
        session_id=f"golden-{case.id}",
        topic_id=topic.id,
        topic_version=topic.version,
        covered_concepts=frozenset(case.prior_covered),
    )
    history = (
        Message(
            id=f"{case.id}-open",
            role=MessageRole.AI_STUDENT,
            content=topic.opening_question,
            turn_number=0,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        ),
    )

    evaluation = evaluator.evaluate(topic, state, history, case.message)
    reduced = StateReducer().apply(topic, state, evaluation, case.message)
    decision = PolicyEngine().choose(topic, reduced)
    reply = student.generate(topic, reduced, decision, history)

    failures: list[str] = []
    if case.forbid_finish and decision.action is Action.FINISH:
        failures.append("kết thúc phiên sớm khi chưa đủ căn cứ")
    if case.expect_action is not None and decision.action is not case.expect_action:
        failures.append(f"action={decision.action.value}, cần {case.expect_action.value}")
    if case.expect_target is not None:
        actual = decision.target.id if decision.target else None
        if actual != case.expect_target:
            failures.append(f"target={actual}, cần {case.expect_target}")
    lowered = reply.casefold()
    for banned in case.reply_must_not_contain:
        if banned.casefold() in lowered:
            failures.append(f"câu trả lời chứa {banned!r}")

    return CaseOutcome(
        case_id=case.id,
        category=case.category,
        action=decision.action.value,
        target=decision.target.id if decision.target else None,
        reply=reply,
        failures=tuple(failures),
    )


def build_report(outcomes: list[CaseOutcome]) -> GoldenReport:
    return GoldenReport(
        total=len(outcomes),
        passed=sum(1 for item in outcomes if item.passed),
        outcomes=outcomes,
    )
