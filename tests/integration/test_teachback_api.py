import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.adapters.evaluator_fake import FixtureEvaluator
from app.factory import PROJECT_ROOT, create_app


def make_test_app() -> FastAPI:
    return create_app(
        evaluator=FixtureEvaluator(PROJECT_ROOT / "tests" / "fixtures" / "evaluator_cases.yaml")
    )


def assert_internal_data_is_hidden(payload: dict[str, object]) -> None:
    serialized = str(payload).lower()
    for forbidden in (
        "evaluation",
        "decision",
        "reason_code",
        "covered_concepts",
        "unclear_concepts",
        "active_misconceptions",
        "next_action",
    ):
        assert forbidden not in serialized


@pytest.mark.anyio
async def test_complete_deterministic_teachback_flow() -> None:
    client = AsyncClient(transport=ASGITransport(app=make_test_app()), base_url="http://test")
    response = await client.post("/topics/kafka_consumer_group/sessions")
    assert response.status_code == 201
    payload = response.json()
    session_id = payload["session_id"]
    assert payload["status"] == "active"
    assert payload["turn_count"] == 0
    assert payload["messages"][0]["role"] == "ai_student"
    assert_internal_data_is_hidden(payload)

    turns = [
        (
            "Consumer group là nhiều consumer cùng xử lý dữ liệu của một topic.",
            "Kafka dựa vào đâu",
        ),
        ("Chúng ở cùng nhóm vì Kafka biết vậy.", "được nhận diện chung bằng gì"),
        (
            "Các consumer có cùng group.id thì thuộc cùng một consumer group.",
            "các partition được chia",
        ),
        ("Mỗi consumer trong group đều nhận mọi message.", "chia tải như thế nào"),
        (
            "À, trong một group, mỗi partition chỉ được giao cho tối đa một consumer "
            "tại một thời điểm.",
            "consumer restart",
        ),
        ("Offset là số message còn lại chưa đọc.", "producer liên tục thêm message"),
        ("Offset là vị trí của record trong một partition.", "tham gia hoặc rời group"),
        (
            "Khi consumer tham gia hoặc rời group, Kafka rebalance và phân phối lại partition.",
            "chưa còn câu hỏi nào",
        ),
    ]

    for number, (message, expected_response_fragment) in enumerate(turns, start=1):
        response = await client.post(
            f"/sessions/{session_id}/messages",
            json={"content": message},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["turn_count"] == number
        assert expected_response_fragment in payload["messages"][-1]["content"]
        assert_internal_data_is_hidden(payload)

    assert payload["status"] == "completed"
    after_finish = await client.post(
        f"/sessions/{session_id}/messages",
        json={"content": "Another answer"},
    )
    assert after_finish.status_code == 409
    await client.aclose()


@pytest.mark.anyio
async def test_get_stop_and_not_found_behaviors() -> None:
    client = AsyncClient(transport=ASGITransport(app=make_test_app()), base_url="http://test")
    missing = await client.get("/sessions/absent")
    assert missing.status_code == 404

    created = (await client.post("/topics/kafka_consumer_group/sessions")).json()
    session_id = created["session_id"]
    stopped = await client.post(f"/sessions/{session_id}/stop")
    assert stopped.status_code == 200
    assert stopped.json()["status"] == "stopped"
    assert_internal_data_is_hidden(stopped.json())

    rejected = await client.post(
        f"/sessions/{session_id}/messages",
        json={"content": "Explanation"},
    )
    assert rejected.status_code == 409
    await client.aclose()


@pytest.mark.anyio
async def test_unknown_fake_evaluator_input_is_conservative() -> None:
    client = AsyncClient(transport=ASGITransport(app=make_test_app()), base_url="http://test")
    created = (await client.post("/topics/kafka_consumer_group/sessions")).json()

    response = await client.post(
        f"/sessions/{created['session_id']}/messages",
        json={"content": "This exact message has no evaluator fixture."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "active"
    assert "phối hợp với nhau" in payload["messages"][-1]["content"]
    assert_internal_data_is_hidden(payload)
    await client.aclose()
