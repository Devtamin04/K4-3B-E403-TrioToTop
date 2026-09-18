from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.teachback.models import MessageRole, SessionStatus, TeachBackSession


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SubmitMessageRequest(ApiModel):
    content: str = Field(min_length=1, max_length=10_000)


class PublicMessage(ApiModel):
    role: MessageRole
    content: str
    turn_number: int
    created_at: datetime


class SessionResponse(ApiModel):
    session_id: str
    topic_id: str
    topic_version: str
    status: SessionStatus
    turn_count: int
    messages: list[PublicMessage]

    @classmethod
    def from_domain(cls, session: TeachBackSession) -> SessionResponse:
        return cls(
            session_id=session.state.session_id,
            topic_id=session.state.topic_id,
            topic_version=session.state.topic_version,
            status=session.state.status,
            turn_count=session.state.turn_count,
            messages=[
                PublicMessage(
                    role=message.role,
                    content=message.content,
                    turn_number=message.turn_number,
                    created_at=message.created_at,
                )
                for message in session.messages
            ],
        )
