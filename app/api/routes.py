from fastapi import APIRouter

from app.api.schemas import SessionResponse, SubmitMessageRequest
from app.teachback.service import TeachBackService


def create_router(service: TeachBackService) -> APIRouter:
    router = APIRouter()

    @router.post(
        "/topics/{topic_id}/sessions",
        response_model=SessionResponse,
        status_code=201,
    )
    async def start_session(topic_id: str) -> SessionResponse:
        return SessionResponse.from_domain(service.start_session(topic_id))

    @router.post("/sessions/{session_id}/messages", response_model=SessionResponse)
    async def submit_message(session_id: str, request: SubmitMessageRequest) -> SessionResponse:
        return SessionResponse.from_domain(service.submit_message(session_id, request.content))

    @router.get("/sessions/{session_id}", response_model=SessionResponse)
    async def get_session(session_id: str) -> SessionResponse:
        return SessionResponse.from_domain(service.get_session(session_id))

    @router.post("/sessions/{session_id}/stop", response_model=SessionResponse)
    async def stop_session(session_id: str) -> SessionResponse:
        return SessionResponse.from_domain(service.stop_session(session_id))

    return router
