from __future__ import annotations

import json
import logging
import re
import time
import unicodedata
from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from app.adapters.student_fake import DeterministicStudentGenerator
from app.llm.errors import (
    LlmInvalidOutputError,
    LlmPermanentError,
    LlmRefusalError,
    LlmTransientError,
)
from app.llm.interfaces import StructuredLlmClient
from app.teachback.models import (
    Action,
    Message,
    PolicyDecision,
    TargetKind,
    TeachBackState,
    TopicDefinition,
)

logger = logging.getLogger(__name__)

MAX_RESPONSE_CHARACTERS = 400

_LEAKAGE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:probe|clarify|challenge|finish)\b", re.IGNORECASE),
    re.compile(r"\b(?:evaluator|evaluation|policy|reducer|rubric)\b", re.IGNORECASE),
    re.compile(r"\bcovered[_ ]concepts?\b", re.IGNORECASE),
    re.compile(r"\bunclear[_ ]concepts?\b", re.IGNORECASE),
    re.compile(r"\bactive[_ ]misconceptions?\b", re.IGNORECASE),
    re.compile(r"\bmisconception\b", re.IGNORECASE),
    re.compile(
        r"\b(?:reason[_ ]code|target[_ ]id|concept[_ ]id|prompt[_ ]version)\b", re.IGNORECASE
    ),
    re.compile(r"\b(?:system|developer)\s+(?:prompt|message|instruction)", re.IGNORECASE),
    re.compile(r"\b(?:hidden|internal)\s+(?:state|instruction|evaluator)", re.IGNORECASE),
    re.compile(r"\bJSON\b"),
)

_CODE_IDENTIFIER = re.compile(r"[A-Za-z]{1,3}\d+")


class StudentOutputPayload(BaseModel):
    """The only field a student LLM is allowed to produce."""

    model_config = ConfigDict(extra="forbid")

    response: str = Field(min_length=1, max_length=MAX_RESPONSE_CHARACTERS)


class StudentResponseRejected(ValueError):
    """The generated reply violated a student constraint and must not be shown."""

    def __init__(self, message: str, *, leaked_internals: bool = False) -> None:
        super().__init__(message)
        self.leaked_internals = leaked_internals


class StudentOutputValidator:
    """Guards the visible reply before it reaches the human teacher.

    These checks are deliberately cheap and deterministic. Semantic qualities
    such as "one main question" are judged by the student evaluation harness,
    not here.
    """

    def validate(
        self,
        *,
        topic: TopicDefinition,
        decision: PolicyDecision,
        response: str,
    ) -> str:
        reply = response.strip()
        if not reply:
            raise StudentResponseRejected("the student reply must not be empty")
        if len(reply) > MAX_RESPONSE_CHARACTERS:
            raise StudentResponseRejected("the student reply is too long")
        if reply.count("?") > 1:
            raise StudentResponseRejected("the student reply must ask at most one question")
        if decision.action not in {Action.FINISH, Action.HALT} and "?" not in reply:
            raise StudentResponseRejected("the student reply must ask its question")

        for pattern in _LEAKAGE_PATTERNS:
            if pattern.search(reply):
                raise StudentResponseRejected(
                    "the student reply exposed internal vocabulary", leaked_internals=True
                )

        normalized = _normalize(reply)
        for identifier in _internal_identifiers(topic):
            if identifier in normalized:
                raise StudentResponseRejected(
                    "the student reply exposed an internal identifier", leaked_internals=True
                )
        return reply


class LlmStudentGenerator:
    """Phrases the next student turn while PolicyEngine keeps deciding what it is.

    The prompt payload carries the chosen action and a curated reference
    question only. Concept descriptions, misconception corrections, learner
    state, evidence, and policy reasoning are never sent, so the model cannot
    leak what it never receives. A reply that still breaks a constraint is
    retried and then replaced by the curated deterministic question.
    """

    PROMPT_VERSION = "student_v1"

    def __init__(
        self,
        *,
        client: StructuredLlmClient,
        model: str,
        prompt_path: Path,
        fallback: DeterministicStudentGenerator | None = None,
        max_attempts: int = 2,
        timeout_seconds: float = 30,
        history_limit: int = 6,
    ) -> None:
        if not model.strip():
            raise ValueError("student model must not be empty")
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if history_limit < 0:
            raise ValueError("history_limit must be non-negative")
        self._client = client
        self._model = model
        self._prompt = prompt_path.read_text(encoding="utf-8")
        self._fallback = fallback or DeterministicStudentGenerator()
        self._max_attempts = max_attempts
        self._timeout_seconds = timeout_seconds
        self._history_limit = history_limit
        self._validator = StudentOutputValidator()

    def opening(self, topic: TopicDefinition) -> str:
        return self._fallback.opening(topic)

    def generate(
        self,
        topic: TopicDefinition,
        state: TeachBackState,
        decision: PolicyDecision,
        history: Sequence[Message],
    ) -> str:
        if decision.action in {Action.FINISH, Action.HALT}:
            return self._fallback.generate(topic, state, decision, history)

        user_input = self._build_input(topic, decision, history)
        request_input = user_input

        for attempt in range(1, self._max_attempts + 1):
            started = time.monotonic()
            try:
                response = self._client.generate_structured(
                    model=self._model,
                    system_prompt=self._prompt,
                    user_input=request_input,
                    output_type=StudentOutputPayload,
                    timeout_seconds=self._timeout_seconds,
                )
                reply = self._validator.validate(
                    topic=topic,
                    decision=decision,
                    response=response.parsed.response,
                )
                logger.info(
                    "Student succeeded prompt_version=%s model=%s action=%s attempt=%d "
                    "latency_ms=%d request_id=%s",
                    self.PROMPT_VERSION,
                    response.model,
                    decision.action,
                    attempt,
                    round((time.monotonic() - started) * 1000),
                    response.request_id,
                )
                return reply
            except (LlmPermanentError, LlmRefusalError):
                logger.warning(
                    "Student unrecoverable failure prompt_version=%s model=%s attempt=%d; "
                    "using the curated question",
                    self.PROMPT_VERSION,
                    self._model,
                    attempt,
                )
                break
            except (LlmTransientError, LlmInvalidOutputError, StudentResponseRejected) as error:
                logger.warning(
                    "Student attempt failed prompt_version=%s model=%s attempt=%d/%d error_type=%s",
                    self.PROMPT_VERSION,
                    self._model,
                    attempt,
                    self._max_attempts,
                    type(error).__name__,
                )
                if isinstance(error, (LlmInvalidOutputError, StudentResponseRejected)):
                    feedback = str(error).replace("\n", " ")[:200]
                    request_input = (
                        f"{user_input}\n\nVALIDATION_FEEDBACK_FROM_PREVIOUS_ATTEMPT: "
                        f"{feedback}. Return a corrected reply."
                    )

        logger.warning(
            "Student falling back to the curated question prompt_version=%s action=%s",
            self.PROMPT_VERSION,
            decision.action,
        )
        return self._fallback.generate(topic, state, decision, history)

    def _build_input(
        self,
        topic: TopicDefinition,
        decision: PolicyDecision,
        history: Sequence[Message],
    ) -> str:
        recent_history = history[-self._history_limit :] if self._history_limit else ()
        latest_human = next(
            (
                message.content
                for message in reversed(recent_history)
                if message.role.value == "human_teacher"
            ),
            "",
        )
        payload = {
            "topic": {"title": topic.title},
            "instruction": {
                "action": decision.action.value,
                "focus": self._focus(topic, decision),
            },
            "recent_conversation": [
                {"role": message.role.value, "content": message.content}
                for message in recent_history
            ],
            "latest_human_message": latest_human,
        }
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _focus(topic: TopicDefinition, decision: PolicyDecision) -> dict[str, str]:
        if decision.target is None:  # Protected by PolicyDecision validation.
            raise ValueError("non-FINISH decision requires a target")
        if decision.target.kind is TargetKind.MISCONCEPTION:
            misconception = topic.misconception(decision.target.id)
            return {
                "kind": "misconception",
                "curated_question": misconception.challenge_question,
                "learner_claim_to_test": misconception.incorrect_claim,
            }
        concept = topic.concept(decision.target.id)
        curated = (
            concept.clarify_question
            if decision.action is Action.CLARIFY
            else concept.probe_question
        )
        return {"kind": "concept", "curated_question": curated}


def _normalize(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold()


def _internal_identifiers(topic: TopicDefinition) -> tuple[str, ...]:
    """Identifier spellings that a student would never utter naturally.

    Single natural words such as "tokenization" are excluded: the teacher uses
    them, so matching them would reject ordinary replies. Machine spellings
    (``context_window``) and opaque codes (``M01``) have no conversational use
    and are treated as leaks.
    """

    candidates = [concept.id for concept in topic.concepts]
    candidates.extend(item.id for item in topic.misconceptions)
    candidates.append(topic.id)
    return tuple(
        _normalize(candidate) for candidate in candidates if not _is_natural_word(candidate)
    )


def _is_natural_word(identifier: str) -> bool:
    return "_" not in identifier and not _CODE_IDENTIFIER.fullmatch(identifier)
