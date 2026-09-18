from __future__ import annotations

from threading import RLock

from app.teachback.exceptions import NotFoundError
from app.teachback.models import TeachBackSession


class InMemorySessionRepository:
    def __init__(self) -> None:
        self._sessions: dict[str, TeachBackSession] = {}
        self._lock = RLock()

    def create(self, session: TeachBackSession) -> None:
        with self._lock:
            session_id = session.state.session_id
            if session_id in self._sessions:
                raise ValueError(f"session {session_id!r} already exists")
            self._sessions[session_id] = session.model_copy(deep=True)

    def get(self, session_id: str) -> TeachBackSession:
        with self._lock:
            try:
                return self._sessions[session_id].model_copy(deep=True)
            except KeyError as error:
                raise NotFoundError(f"session {session_id!r} was not found") from error

    def save(self, session: TeachBackSession) -> None:
        with self._lock:
            session_id = session.state.session_id
            if session_id not in self._sessions:
                raise NotFoundError(f"session {session_id!r} was not found")
            self._sessions[session_id] = session.model_copy(deep=True)
