from __future__ import annotations

import json
import logging
import time
import unicodedata
from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.llm.errors import (
    LlmInvalidOutputError,
    LlmPermanentError,
    LlmRefusalError,
    LlmTransientError,
)
from app.llm.interfaces import StructuredLlmClient
from app.teachback.exceptions import EvaluationFailedError, InvalidEvaluationError
from app.teachback.models import (
    EvaluationResult,
    Evidence,
    Judgment,
    Message,
    TeachBackState,
    TopicDefinition,
)

logger = logging.getLogger(__name__)


class EvaluatorEvidencePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    concept_id: str = Field(min_length=1)
    user_quote: str = Field(min_length=1)
    judgment: Judgment
    explanation: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)


class EvaluatorOutputPayload(BaseModel):
    """The only fields an evaluator LLM is allowed to produce."""

    model_config = ConfigDict(extra="forbid")

    covered: list[str] = Field(default_factory=list)
    unclear: list[str] = Field(default_factory=list)
    misconceptions: list[str] = Field(default_factory=list)
    resolved_misconceptions: list[str] = Field(default_factory=list)
    evidence: list[EvaluatorEvidencePayload] = Field(default_factory=list)
    recommended_target: str | None = None
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_classifications(self) -> EvaluatorOutputPayload:
        named_lists = {
            "covered": self.covered,
            "unclear": self.unclear,
            "misconceptions": self.misconceptions,
            "resolved_misconceptions": self.resolved_misconceptions,
        }
        for name, values in named_lists.items():
            if len(values) != len(set(values)):
                raise ValueError(f"{name} must not contain duplicate IDs")
        if set(self.covered) & set(self.unclear):
            raise ValueError("a concept cannot be covered and unclear in one evaluation")
        if set(self.misconceptions) & set(self.resolved_misconceptions):
            raise ValueError("a misconception cannot be detected and resolved in one evaluation")
        return self


class EvaluationOutputValidator:
    """Validates LLM semantics before EvaluationResult reaches StateReducer."""

    def validate(
        self,
        *,
        topic: TopicDefinition,
        state: TeachBackState,
        payload: EvaluatorOutputPayload,
        latest_user_message: str,
    ) -> EvaluationResult:
        concept_ids = {concept.id for concept in topic.concepts}
        misconception_ids = {item.id for item in topic.misconceptions}
        unknown_concepts = (set(payload.covered) | set(payload.unclear)) - concept_ids
        unknown_evidence = {item.concept_id for item in payload.evidence} - concept_ids
        unknown_misconceptions = (
            set(payload.misconceptions) | set(payload.resolved_misconceptions)
        ) - misconception_ids
        if unknown_concepts or unknown_evidence or unknown_misconceptions:
            raise InvalidEvaluationError(
                "evaluation references unknown IDs: "
                f"concepts={sorted(unknown_concepts | unknown_evidence)}, "
                f"misconceptions={sorted(unknown_misconceptions)}"
            )

        if payload.recommended_target is not None:
            valid_targets = concept_ids | misconception_ids
            if payload.recommended_target not in valid_targets:
                raise InvalidEvaluationError("recommended target references an unknown ID")

        canonical_evidence: list[Evidence] = []
        for item in payload.evidence:
            exact_quote = find_exact_normalized_span(latest_user_message, item.user_quote)
            if exact_quote is None:
                raise InvalidEvaluationError(
                    "evidence quote must originate from the latest user message"
                )
            canonical_evidence.append(
                Evidence(
                    concept_id=item.concept_id,
                    user_quote=exact_quote,
                    judgment=item.judgment,
                    explanation=item.explanation,
                    confidence=item.confidence,
                    turn=state.turn_count + 1,
                )
            )

        correct_ids = {
            item.concept_id for item in canonical_evidence if item.judgment is Judgment.CORRECT
        }
        unclear_ids = {
            item.concept_id for item in canonical_evidence if item.judgment is Judgment.UNCLEAR
        }
        incorrect_ids = {
            item.concept_id for item in canonical_evidence if item.judgment is Judgment.INCORRECT
        }
        if not set(payload.covered) <= correct_ids:
            raise InvalidEvaluationError("every covered concept requires correct evidence")
        if not set(payload.unclear) <= unclear_ids:
            raise InvalidEvaluationError("every unclear concept requires unclear evidence")

        for misconception_id in payload.misconceptions:
            concept_id = topic.misconception(misconception_id).concept_id
            if concept_id not in incorrect_ids:
                raise InvalidEvaluationError(
                    f"detected misconception {misconception_id} requires incorrect evidence"
                )
        for misconception_id in payload.resolved_misconceptions:
            if misconception_id not in state.active_misconceptions:
                raise InvalidEvaluationError(
                    f"resolved misconception {misconception_id} is not active"
                )
            concept_id = topic.misconception(misconception_id).concept_id
            if concept_id not in payload.covered or concept_id not in correct_ids:
                raise InvalidEvaluationError(
                    f"resolved misconception {misconception_id} requires correct concept coverage"
                )

        return EvaluationResult(
            covered=payload.covered,
            unclear=payload.unclear,
            misconceptions=payload.misconceptions,
            resolved_misconceptions=payload.resolved_misconceptions,
            evidence=canonical_evidence,
            recommended_target=payload.recommended_target,
            confidence=payload.confidence,
        )


class LlmEvaluator:
    PROMPT_VERSION = "evaluator_v1"

    def __init__(
        self,
        *,
        client: StructuredLlmClient,
        model: str,
        prompt_path: Path,
        max_attempts: int = 2,
        timeout_seconds: float = 30,
        history_limit: int = 12,
    ) -> None:
        if not model.strip():
            raise ValueError("evaluator model must not be empty")
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if history_limit < 0:
            raise ValueError("history_limit must be non-negative")
        self._client = client
        self._model = model
        self._prompt = prompt_path.read_text(encoding="utf-8")
        self._max_attempts = max_attempts
        self._timeout_seconds = timeout_seconds
        self._history_limit = history_limit
        self._validator = EvaluationOutputValidator()

    def evaluate(
        self,
        topic: TopicDefinition,
        state: TeachBackState,
        history: Sequence[Message],
        latest_user_message: str,
    ) -> EvaluationResult:
        user_input = self._build_input(topic, state, history, latest_user_message)
        request_input = user_input
        last_error: Exception | None = None

        for attempt in range(1, self._max_attempts + 1):
            started = time.monotonic()
            try:
                response = self._client.generate_structured(
                    model=self._model,
                    system_prompt=self._prompt,
                    user_input=request_input,
                    output_type=EvaluatorOutputPayload,
                    timeout_seconds=self._timeout_seconds,
                )
                result = self._validator.validate(
                    topic=topic,
                    state=state,
                    payload=response.parsed,
                    latest_user_message=latest_user_message,
                )
                logger.info(
                    "Evaluator succeeded prompt_version=%s model=%s attempt=%d "
                    "latency_ms=%d request_id=%s",
                    self.PROMPT_VERSION,
                    response.model,
                    attempt,
                    round((time.monotonic() - started) * 1000),
                    response.request_id,
                )
                return result
            except LlmPermanentError as error:
                logger.exception(
                    "Evaluator permanent failure prompt_version=%s model=%s attempt=%d",
                    self.PROMPT_VERSION,
                    self._model,
                    attempt,
                )
                raise EvaluationFailedError(
                    "evaluator configuration or request was rejected"
                ) from error
            except LlmRefusalError as error:
                logger.warning(
                    "Evaluator refusal prompt_version=%s model=%s attempt=%d",
                    self.PROMPT_VERSION,
                    self._model,
                    attempt,
                )
                raise EvaluationFailedError("evaluator declined the request") from error
            except (LlmTransientError, LlmInvalidOutputError, InvalidEvaluationError) as error:
                last_error = error
                logger.warning(
                    "Evaluator attempt failed prompt_version=%s model=%s attempt=%d/%d "
                    "error_type=%s",
                    self.PROMPT_VERSION,
                    self._model,
                    attempt,
                    self._max_attempts,
                    type(error).__name__,
                )
                if isinstance(error, (LlmInvalidOutputError, InvalidEvaluationError)):
                    feedback = str(error).replace("\n", " ")[:500]
                    request_input = (
                        f"{user_input}\n\nVALIDATION_FEEDBACK_FROM_PREVIOUS_ATTEMPT: "
                        f"{feedback}. Return a corrected structured evaluation."
                    )

        raise EvaluationFailedError(
            f"evaluator failed after {self._max_attempts} attempts"
        ) from last_error

    def _build_input(
        self,
        topic: TopicDefinition,
        state: TeachBackState,
        history: Sequence[Message],
        latest_user_message: str,
    ) -> str:
        recent_history = history[-self._history_limit :] if self._history_limit else ()
        payload = {
            "topic": {
                "id": topic.id,
                "version": topic.version,
                "title": topic.title,
                "concepts": [
                    {
                        "id": concept.id,
                        "required": concept.required,
                        "description": concept.description,
                    }
                    for concept in topic.concepts
                ],
                "known_misconceptions": [
                    {
                        "id": item.id,
                        "concept_id": item.concept_id,
                        "incorrect_claim": item.incorrect_claim,
                        "correction": item.correction,
                    }
                    for item in topic.misconceptions
                ],
            },
            "current_state": {
                "covered_concepts": sorted(state.covered_concepts),
                "unclear_concepts": sorted(state.unclear_concepts),
                "active_misconceptions": sorted(state.active_misconceptions),
                "turn_count": state.turn_count,
            },
            "recent_conversation": [
                {
                    "role": message.role.value,
                    "content": message.content,
                    "turn_number": message.turn_number,
                }
                for message in recent_history
            ],
            "latest_human_message": latest_user_message,
        }
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def normalize_evidence_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split())


def find_exact_normalized_span(source: str, candidate: str) -> str | None:
    """Return an exact source span after Unicode/whitespace-normalized matching.

    The returned value always comes verbatim from ``source``. This lets the
    evaluator accept harmless normalization differences without accepting a
    paraphrase or invented quote.
    """

    normalized_candidate = normalize_evidence_text(candidate)
    if not normalized_candidate:
        return None
    if candidate in source:
        return candidate

    normalized_source, starts, ends = _normalize_with_source_map(source)
    match_start = normalized_source.find(normalized_candidate)
    if match_start < 0:
        return None
    match_end = match_start + len(normalized_candidate) - 1
    return source[starts[match_start] : ends[match_end]]


def _normalize_with_source_map(value: str) -> tuple[str, list[int], list[int]]:
    output: list[str] = []
    starts: list[int] = []
    ends: list[int] = []
    index = 0
    pending_space: tuple[int, int] | None = None

    while index < len(value):
        start = index
        if value[index].isspace():
            index += 1
            while index < len(value) and value[index].isspace():
                index += 1
            if output:
                pending_space = (start, index)
            continue

        index += 1
        while index < len(value) and unicodedata.combining(value[index]):
            index += 1
        normalized_unit = unicodedata.normalize("NFKC", value[start:index])

        if pending_space is not None:
            output.append(" ")
            starts.append(pending_space[0])
            ends.append(pending_space[1])
            pending_space = None

        for character in normalized_unit:
            output.append(character)
            starts.append(start)
            ends.append(index)

    return "".join(output), starts, ends
