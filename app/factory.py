from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.adapters.sessions_memory import InMemorySessionRepository
from app.adapters.student_fake import DeterministicStudentGenerator
from app.adapters.topics_yaml import YamlTopicRepository
from app.api.routes import create_router
from app.teachback.exceptions import (
    EvaluationFailedError,
    NotFoundError,
    SessionNotActiveError,
)
from app.teachback.interfaces import Evaluator
from app.teachback.service import TeachBackService

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def create_app(
    *,
    evaluator: Evaluator,
    topic_directory: Path | None = None,
) -> FastAPI:
    topics = YamlTopicRepository(topic_directory or PROJECT_ROOT / "knowledge")
    sessions = InMemorySessionRepository()
    service = TeachBackService(
        topics=topics,
        sessions=sessions,
        evaluator=evaluator,
        student=DeterministicStudentGenerator(),
    )

    application = FastAPI(title="Teach-Back AI", version="0.2.0")

    @application.exception_handler(NotFoundError)
    async def not_found_handler(request: Request, error: NotFoundError) -> JSONResponse:
        del request
        return JSONResponse(status_code=404, content={"detail": str(error)})

    @application.exception_handler(SessionNotActiveError)
    async def session_conflict_handler(
        request: Request, error: SessionNotActiveError
    ) -> JSONResponse:
        del request
        return JSONResponse(status_code=409, content={"detail": str(error)})

    @application.exception_handler(EvaluationFailedError)
    async def evaluation_failure_handler(
        request: Request, error: EvaluationFailedError
    ) -> JSONResponse:
        del request, error
        return JSONResponse(
            status_code=503,
            content={"detail": "The hidden evaluator is temporarily unavailable."},
        )

    application.include_router(create_router(service))
    return application
