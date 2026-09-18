from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

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
    layer: Literal["1", "2", "3", "4"] = "4"
    """Lớp chỗ khó theo guide §2.5: ①nguồn sự thật ②mơ hồ ③ngoài phạm vi ④đặc thù domain."""
    source: Literal["tu_xay", "chatlog"] = "tu_xay"
    message: str = Field(min_length=1)
    grid: str = ""
    prior_covered: list[str] = Field(default_factory=list)
    expect_action: Action | None = None
    expect_target: str | None = None
    forbid_finish: bool = False
    forbid_halt: bool = False
    reply_must_not_contain: list[str] = Field(default_factory=list)
    expect_fail: str = ""
    """Lý do nhóm dự đoán case này trượt; để trống nghĩa là kỳ vọng ĐẠT."""
    note: str = ""


@dataclass(frozen=True, slots=True)
class CaseOutcome:
    case_id: str
    category: str
    action: str
    target: str | None
    reply: str
    failures: tuple[str, ...]
    message: str = ""
    grid: str = ""
    layer: str = ""
    source: str = ""
    predicted_fail: bool = False

    @property
    def passed(self) -> bool:
        return not self.failures

    @property
    def prediction_held(self) -> bool:
        """Nhóm đoán trượt và nó trượt thật, hoặc đoán đạt và nó đạt."""

        return self.predicted_fail != self.passed


@dataclass(frozen=True, slots=True)
class GoldenReport:
    total: int
    passed: int
    outcomes: list[CaseOutcome] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total else 0.0

    def by_category(self) -> dict[str, tuple[int, int]]:
        return self._tally(lambda item: item.category)

    def by_layer(self) -> dict[str, tuple[int, int]]:
        """Độ phủ theo 4 lớp chỗ khó — TA soát theo bảng này."""

        return self._tally(lambda item: item.layer)

    def _tally(self, key: Callable[[CaseOutcome], str]) -> dict[str, tuple[int, int]]:
        table: dict[str, list[int]] = {}
        for outcome in self.outcomes:
            row = table.setdefault(key(outcome), [0, 0])
            row[1] += 1
            if outcome.passed:
                row[0] += 1
        return {name: (value[0], value[1]) for name, value in table.items()}


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
    if case.forbid_halt and decision.action is Action.HALT:
        failures.append("bỏ cuộc dù người học vẫn đang tham gia")
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
        message=case.message,
        grid=case.grid,
        layer=case.layer,
        source=case.source,
        predicted_fail=bool(case.expect_fail),
    )


def build_report(outcomes: list[CaseOutcome]) -> GoldenReport:
    return GoldenReport(
        total=len(outcomes),
        passed=sum(1 for item in outcomes if item.passed),
        outcomes=outcomes,
    )


def write_run_artifacts(
    report: GoldenReport,
    *,
    directory: Path,
    trace_directory: Path,
    model: str,
    prompt_version: str,
    quality_bar: float,
) -> tuple[Path, Path]:
    """Ghi bảng kết quả vào eval/ và trace lời gọi AI vào logs/traces/."""

    directory.mkdir(parents=True, exist_ok=True)
    trace_directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")

    trace_path = trace_directory / f"{stamp}-trace.json"
    trace_path.write_text(
        json.dumps(
            {
                "run_at": stamp,
                "model": model,
                "prompt_version": prompt_version,
                "quality_bar": quality_bar,
                "total": report.total,
                "passed": report.passed,
                "pass_rate": round(report.pass_rate, 4),
                "cases": [
                    {
                        "case_id": item.case_id,
                        "category": item.category,
                        "grid": item.grid,
                        "layer": item.layer,
                        "source": item.source,
                        "input": item.message,
                        "action": item.action,
                        "target": item.target,
                        "output": item.reply,
                        "passed": item.passed,
                        "predicted_fail": item.predicted_fail,
                        "failures": list(item.failures),
                    }
                    for item in report.outcomes
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    table_path = directory / f"{stamp}-results.md"
    lines = [
        f"# Lượt đo golden set — {stamp}",
        "",
        f"- Model: `{model}` · prompt: `{prompt_version}`",
        f"- Quality bar: **{quality_bar:.0%}**",
        f"- Kết quả: **{report.passed}/{report.total} = {report.pass_rate:.1%}** "
        f"→ {'ĐẠT' if report.pass_rate >= quality_bar else 'CHƯA ĐẠT'}",
        "",
        "| case | input | output | đạt? |",
        "|---|---|---|---|",
    ]
    for item in report.outcomes:
        verdict = "ĐẠT" if item.passed else f"KHÔNG — {'; '.join(item.failures)}"
        lines.append(
            f"| `{item.case_id}` | {_cell(item.message)} | "
            f"{item.action} {item.target or ''} · {_cell(item.reply)} | {verdict} |"
        )
    table_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return table_path, trace_path


def _cell(text: str, limit: int = 110) -> str:
    flat = " ".join(text.split())
    if len(flat) > limit:
        flat = f"{flat[:limit]}…"
    return flat.replace("|", "\\|")
