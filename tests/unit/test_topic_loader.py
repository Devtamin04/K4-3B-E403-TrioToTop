from pathlib import Path

import pytest

from app.adapters.topics_yaml import YamlTopicRepository
from app.teachback.exceptions import NotFoundError


def test_loads_topic_and_preserves_declared_priority_order(tmp_path: Path) -> None:
    (tmp_path / "topic.yaml").write_text(
        """
id: test
version: '1'
title: Test
opening_question: Teach me?
completion_message: Thanks.
concepts:
  - id: later
    description: Later
    required: true
    priority: 20
    probe_question: Later?
    clarify_question: Clarify later?
  - id: first
    description: First
    required: true
    priority: 10
    probe_question: First?
    clarify_question: Clarify first?
""".strip(),
        encoding="utf-8",
    )

    topic = YamlTopicRepository(tmp_path).get("test")

    assert [concept.id for concept in topic.concepts] == ["later", "first"]
    assert topic.required_concept_ids == frozenset({"later", "first"})


def test_rejects_unknown_misconception_concept(tmp_path: Path) -> None:
    (tmp_path / "bad.yaml").write_text(
        """
id: bad
version: '1'
title: Bad
opening_question: Teach me?
completion_message: Thanks.
concepts:
  - id: known
    description: Known
    required: true
    priority: 10
    probe_question: Known?
    clarify_question: Clarify?
misconceptions:
  - id: M1
    concept_id: absent
    incorrect_claim: Wrong
    correction: Right
    priority: 10
    challenge_question: Really?
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unknown concepts"):
        YamlTopicRepository(tmp_path)


def test_unknown_topic_is_not_found(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / "knowledge" / "kafka_consumer_group.yaml"
    (tmp_path / "topic.yaml").write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    repository = YamlTopicRepository(tmp_path)

    with pytest.raises(NotFoundError):
        repository.get("absent")
