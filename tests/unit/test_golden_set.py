from __future__ import annotations

from pathlib import Path

from app.adapters.topics_yaml import YamlTopicRepository
from evals.golden import CaseOutcome, GoldenCase, build_report, load_golden_set

ROOT = Path(__file__).resolve().parents[2]


def _cases() -> list[GoldenCase]:
    return load_golden_set(ROOT / "evals" / "golden_set.yaml")


def test_golden_set_has_at_least_twenty_cases() -> None:
    assert len(_cases()) >= 20


def test_every_case_references_real_ids() -> None:
    topic = YamlTopicRepository(ROOT / "knowledge").get("context_window")
    concept_ids = {concept.id for concept in topic.concepts}
    misconception_ids = {item.id for item in topic.misconceptions}

    for case in _cases():
        assert set(case.prior_covered) <= concept_ids, case.id
        if case.expect_target is not None:
            assert case.expect_target in concept_ids | misconception_ids, case.id


def test_categories_cover_the_three_difficulty_levels() -> None:
    assert {"thuong", "kho", "hiem"} <= {case.category for case in _cases()}


def test_adversarial_cases_forbid_finishing() -> None:
    """Case tấn công phải luôn cấm kết thúc phiên, nếu không tiêu chí là vô nghĩa."""

    for case in _cases():
        if case.category in {"kho", "hiem"}:
            assert case.forbid_finish, case.id


def test_report_counts_only_cases_without_failures() -> None:
    outcomes = [
        CaseOutcome("a", "thuong", "PROBE", "token_unit", "ok?", ()),
        CaseOutcome("b", "kho", "FINISH", None, "xong", ("kết thúc sớm",)),
    ]

    report = build_report(outcomes)

    assert report.total == 2
    assert report.passed == 1
    assert report.pass_rate == 0.5
    assert report.by_category() == {"thuong": (1, 1), "kho": (0, 1)}
