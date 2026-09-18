from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from app.teachback.exceptions import SessionNotActiveError
from app.teachback.interfaces import Evaluator, SessionRepository, StudentGenerator, TopicRepository
from app.teachback.models import (
    Action,
    Message,
    MessageRole,
    SessionStatus,
    TeachBackSession,
    TeachBackState,
    TopicDefinition,
    TurnRecord,
)
from app.teachback.policy import PolicyEngine
from app.teachback.state import StateReducer


class TeachBackService:
    def __init__(
        self,
        topics: TopicRepository,
        sessions: SessionRepository,
        evaluator: Evaluator,
        student: StudentGenerator,
        *,
        id_factory: Callable[[], str] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._topics = topics
        self._sessions = sessions
        self._evaluator = evaluator
        self._student = student
        self._reducer = StateReducer()
        self._policy = PolicyEngine()
        self._id_factory = id_factory or (lambda: str(uuid4()))
        self._clock = clock or (lambda: datetime.now(UTC))

    def list_topics(self) -> list[TopicDefinition]:
        return self._topics.list_topics()

    def start_session(self, topic_id: str) -> TeachBackSession:
        topic = self._topics.get(topic_id)
        session_id = self._id_factory()
        state = TeachBackState(
            session_id=session_id,
            topic_id=topic.id,
            topic_version=topic.version,
        )
        opening = Message(
            id=self._id_factory(),
            role=MessageRole.AI_STUDENT,
            content=self._student.opening(topic),
            turn_number=0,
            created_at=self._clock(),
        )
        session = TeachBackSession(state=state, messages=(opening,))
        self._sessions.create(session)
        return session

    def submit_message(self, session_id: str, content: str) -> TeachBackSession:
        session = self._sessions.get(session_id)
        if session.state.status is not SessionStatus.ACTIVE:
            raise SessionNotActiveError(
                f"session {session_id} is {session.state.status} and cannot accept messages"
            )

        topic = self._topics.get(session.state.topic_id)
        if topic.version != session.state.topic_version:
            raise SessionNotActiveError("the session's pinned topic version is unavailable")

        turn = session.state.turn_count + 1
        user_message = Message(
            id=self._id_factory(),
            role=MessageRole.HUMAN_TEACHER,
            content=content,
            turn_number=turn,
            created_at=self._clock(),
        )
        evaluation = self._evaluator.evaluate(topic, session.state, session.messages, content)
        reduced_state = self._reducer.apply(topic, session.state, evaluation, content)
        decision = self._policy.choose(topic, reduced_state)
        student_response = self._student.generate(
            topic,
            reduced_state,
            decision,
            (*session.messages, user_message),
        )

        status = (
            SessionStatus.COMPLETED if decision.action is Action.FINISH else SessionStatus.ACTIVE
        )
        next_state = reduced_state.model_copy(
            update={
                "current_target": decision.target,
                "next_action": decision.action,
                "status": status,
            }
        )
        student_message = Message(
            id=self._id_factory(),
            role=MessageRole.AI_STUDENT,
            content=student_response,
            turn_number=turn,
            created_at=self._clock(),
        )
        record = TurnRecord(
            turn_number=turn,
            evaluation=evaluation,
            decision=decision,
            student_response=student_response,
        )
        updated = TeachBackSession(
            state=next_state,
            messages=(*session.messages, user_message, student_message),
            turn_records=(*session.turn_records, record),
        )
        self._sessions.save(updated)
        return updated

    def get_session(self, session_id: str) -> TeachBackSession:
        return self._sessions.get(session_id)

    def stop_session(self, session_id: str) -> TeachBackSession:
        session = self._sessions.get(session_id)
        if session.state.status is not SessionStatus.ACTIVE:
            raise SessionNotActiveError(
                f"session {session_id} is {session.state.status} and cannot be stopped"
            )
        stopped = session.model_copy(
            update={"state": session.state.model_copy(update={"status": SessionStatus.STOPPED})}
        )
        self._sessions.save(stopped)
        return stopped
