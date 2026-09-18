from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from app.teachback.exceptions import NotFoundError
from app.teachback.models import TopicDefinition


class YamlTopicRepository:
    def __init__(self, directory: Path) -> None:
        self._topics: dict[str, TopicDefinition] = {}
        for path in sorted(directory.glob("*.yaml")):
            topic = self._load(path)
            if topic.id in self._topics:
                raise ValueError(f"duplicate topic ID {topic.id!r}")
            self._topics[topic.id] = topic
        if not self._topics:
            raise ValueError(f"no topic YAML files found in {directory}")

    def get(self, topic_id: str) -> TopicDefinition:
        try:
            return self._topics[topic_id]
        except KeyError as error:
            raise NotFoundError(f"topic {topic_id!r} was not found") from error

    @staticmethod
    def _load(path: Path) -> TopicDefinition:
        try:
            raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
            return TopicDefinition.model_validate(raw)
        except (OSError, yaml.YAMLError, ValidationError) as error:
            raise ValueError(f"invalid topic file {path}: {error}") from error
