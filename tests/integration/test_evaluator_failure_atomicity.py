from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.factory import create_app
from app.teachback.exceptions import EvaluationFailedError
from app.teachback.models import EvaluationResult


class FailingEvaluator:
    def evaluate(self, *args: object, **kwargs: object) -> EvaluationResult:
        del args, kwargs
        raise EvaluationFailedError("sensitive provider detail")


@pytest.mark.anyio
async def test_failed_evaluation_returns_503_without_mutating_session() -> None:
    client = AsyncClient(
        transport=ASGITransport(app=create_app(evaluator=FailingEvaluator())),
        base_url="http://test",
    )
    created = (await client.post("/topics/kafka_consumer_group/sessions")).json()
    session_id = created["session_id"]

    failed = await client.post(
        f"/sessions/{session_id}/messages",
        json={"content": "A message that cannot be evaluated."},
    )
    after = (await client.get(f"/sessions/{session_id}")).json()

    assert failed.status_code == 503
    assert failed.json() == {"detail": "The hidden evaluator is temporarily unavailable."}
    assert "sensitive" not in failed.text
    assert after == created
    await client.aclose()
