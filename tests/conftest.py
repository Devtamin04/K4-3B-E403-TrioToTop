from pathlib import Path

import pytest

from app.adapters.topics_yaml import YamlTopicRepository
from app.teachback.models import TopicDefinition

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def topic() -> TopicDefinition:
    return YamlTopicRepository(ROOT / "knowledge").get("kafka_consumer_group")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
