from __future__ import annotations

from collections import Counter
from pathlib import Path

from app.adapters.topics_yaml import YamlTopicRepository
from eval_harness.golden import CaseOutcome, GoldenCase, build_report, load_golden_set

ROOT = Path(__file__).resolve().parents[2]


def _cases() -> list[GoldenCase]:
    return load_golden_set(ROOT / "eval_harness" / "datasets" / "golden_set.yaml")


def test_golden_set_has_at_least_twenty_five_cases() -> None:
    assert len(_cases()) >= 25


def test_every_case_references_real_ids() -> None:
    topic = YamlTopicRepository(ROOT / "knowledge").get("context_window")
    concept_ids = {concept.id for concept in topic.concepts}
    misconception_ids = {item.id for item in topic.misconceptions}

    for case in _cases():
        assert set(case.prior_covered) <= concept_ids, case.id
        if case.expect_target is not None:
            assert case.expect_target in concept_ids | misconception_ids, case.id


def test_every_difficulty_layer_has_at_least_two_cases() -> None:
    """Guide §2.5: mỗi lớp chỗ khó phải có ≥2 case trong golden set."""

    counts = Counter(case.layer for case in _cases())
    for layer in ("1", "2", "3", "4"):
        assert counts[layer] >= 2, f"lớp {layer} chỉ có {counts[layer]} case"


def test_some_cases_come_from_real_chatlog() -> None:
    """Case từ chatlog thật phải ghi nguồn truy vết được."""

    from_log = [case for case in _cases() if case.source == "chatlog"]
    assert len(from_log) >= 5
    for case in from_log:
        assert "T0" in case.note, f"{case.id} thiếu turn_id dẫn nguồn"


def test_at_least_five_cases_are_predicted_to_fail() -> None:
    """Bộ đề phải gồm case nhóm tin là sẽ trượt, kèm lý do phân tích được."""

    predicted = [case for case in _cases() if case.expect_fail]
    assert len(predicted) >= 5
    for case in predicted:
        assert len(case.expect_fail.split()) >= 10, f"{case.id} thiếu phân tích nguyên nhân"


def test_adversarial_cases_forbid_finishing() -> None:
    """Case tấn công phải luôn cấm kết thúc phiên, nếu không tiêu chí là vô nghĩa."""

    for case in _cases():
        if case.category in {"tan_cong", "hieu_sai"}:
            assert case.forbid_finish, case.id


def test_every_case_declares_its_grid_cell() -> None:
    """Không có case nào thêm theo cảm giác: mỗi case phải gắn vào một ô lưới."""

    for case in _cases():
        assert case.grid.count("·") >= 2, case.id


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
