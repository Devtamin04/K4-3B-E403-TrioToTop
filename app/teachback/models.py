from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DomainModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Action(StrEnum):
    CHALLENGE = "CHALLENGE"
    CLARIFY = "CLARIFY"
    PROBE = "PROBE"
    FINISH = "FINISH"


class Judgment(StrEnum):
    CORRECT = "correct"
    INCORRECT = "incorrect"
    UNCLEAR = "unclear"


class SessionStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    STOPPED = "stopped"


class MessageRole(StrEnum):
    HUMAN_TEACHER = "human_teacher"
    AI_STUDENT = "ai_student"


class TargetKind(StrEnum):
    CONCEPT = "concept"
    MISCONCEPTION = "misconception"


class CoveragePolicy(StrEnum):
    ALL_ELEMENTS = "all_elements"
    ANY_ELEMENT = "any_element"


class ConceptElement(DomainModel):
    """A unit of understanding the learner must demonstrate themselves.

    Distinct from ``ConceptDefinition.description``, which states what is true.
    An element states what the learner's own words must show, so it must never
    contain a literal answer string.
    """

    id: str = Field(min_length=1)
    description: str = Field(min_length=1)


class ConceptDefinition(DomainModel):
    id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    required: bool = True
    priority: int = Field(ge=0)
    probe_question: str = Field(min_length=1)
    clarify_question: str = Field(min_length=1)
    required_elements: list[ConceptElement] = Field(default_factory=list)
    coverage_policy: CoveragePolicy = CoveragePolicy.ALL_ELEMENTS

    @model_validator(mode="after")
    def validate_elements(self) -> ConceptDefinition:
        element_ids = [element.id for element in self.required_elements]
        if len(element_ids) != len(set(element_ids)):
            raise ValueError(f"concept {self.id} has duplicate element IDs")
        return self

    @property
    def element_ids(self) -> frozenset[str]:
        return frozenset(element.id for element in self.required_elements)

    def elements_satisfy_policy(self, demonstrated: frozenset[str]) -> bool:
        """Whether demonstrated elements are enough for this concept."""

        required = self.element_ids
        if not required:
            return True
        satisfied = required & demonstrated
        if self.coverage_policy is CoveragePolicy.ANY_ELEMENT:
            return bool(satisfied)
        return satisfied == required


class MisconceptionDefinition(DomainModel):
    id: str = Field(min_length=1)
    concept_id: str = Field(min_length=1)
    incorrect_claim: str = Field(min_length=1)
    correction: str = Field(min_length=1)
    priority: int = Field(ge=0)
    challenge_question: str = Field(min_length=1)


class TopicDefinition(DomainModel):
    id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    title: str = Field(min_length=1)
    opening_question: str = Field(min_length=1)
    completion_message: str = Field(min_length=1)
    concepts: list[ConceptDefinition] = Field(min_length=1)
    misconceptions: list[MisconceptionDefinition] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_references(self) -> TopicDefinition:
        concept_ids = [concept.id for concept in self.concepts]
        if len(concept_ids) != len(set(concept_ids)):
            raise ValueError("topic concept IDs must be unique")

        misconception_ids = [item.id for item in self.misconceptions]
        if len(misconception_ids) != len(set(misconception_ids)):
            raise ValueError("topic misconception IDs must be unique")

        unknown = {
            item.concept_id for item in self.misconceptions if item.concept_id not in concept_ids
        }
        if unknown:
            raise ValueError(f"misconceptions reference unknown concepts: {sorted(unknown)}")
        if not any(concept.required for concept in self.concepts):
            raise ValueError("topic must contain at least one required concept")
        return self

    @property
    def required_concept_ids(self) -> frozenset[str]:
        return frozenset(concept.id for concept in self.concepts if concept.required)

    def concept(self, concept_id: str) -> ConceptDefinition:
        for concept in self.concepts:
            if concept.id == concept_id:
                return concept
        raise KeyError(concept_id)

    def misconception(self, misconception_id: str) -> MisconceptionDefinition:
        for misconception in self.misconceptions:
            if misconception.id == misconception_id:
                return misconception
        raise KeyError(misconception_id)


class Evidence(DomainModel):
    concept_id: str = Field(min_length=1)
    user_quote: str = Field(min_length=1)
    judgment: Judgment
    explanation: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    turn: int = Field(ge=1)
    demonstrated_elements: list[str] = Field(default_factory=list)
    inference_used: bool = False


class EvaluationResult(DomainModel):
    """Per-turn observations. Accumulation belongs exclusively to StateReducer."""

    covered: list[str] = Field(default_factory=list)
    unclear: list[str] = Field(default_factory=list)
    misconceptions: list[str] = Field(default_factory=list)
    resolved_misconceptions: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    recommended_target: str | None = None
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_classifications(self) -> EvaluationResult:
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
            raise ValueError("a concept cannot be covered and unclear in the same evaluation")
        if set(self.misconceptions) & set(self.resolved_misconceptions):
            raise ValueError(
                "a misconception cannot be detected and resolved in the same evaluation"
            )
        return self


class Target(DomainModel):
    kind: TargetKind
    id: str = Field(min_length=1)


class PolicyDecision(DomainModel):
    action: Action
    target: Target | None
    reason_code: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_target(self) -> PolicyDecision:
        if self.action is Action.FINISH and self.target is not None:
            raise ValueError("FINISH must not have a target")
        if self.action is not Action.FINISH and self.target is None:
            raise ValueError(f"{self.action} requires a target")
        return self


class TeachBackState(DomainModel):
    session_id: str = Field(min_length=1)
    topic_id: str = Field(min_length=1)
    topic_version: str = Field(min_length=1)
    covered_concepts: frozenset[str] = Field(default_factory=frozenset)
    unclear_concepts: frozenset[str] = Field(default_factory=frozenset)
    active_misconceptions: frozenset[str] = Field(default_factory=frozenset)
    evidence: tuple[Evidence, ...] = ()
    current_target: Target | None = None
    next_action: Action | None = None
    turn_count: int = Field(default=0, ge=0)
    status: SessionStatus = SessionStatus.ACTIVE


class Message(DomainModel):
    id: str = Field(min_length=1)
    role: MessageRole
    content: str = Field(min_length=1)
    turn_number: int = Field(ge=0)
    created_at: datetime


class TurnRecord(DomainModel):
    turn_number: int = Field(ge=1)
    evaluation: EvaluationResult
    decision: PolicyDecision
    student_response: str = Field(min_length=1)


class TeachBackSession(DomainModel):
    state: TeachBackState
    messages: tuple[Message, ...] = ()
    turn_records: tuple[TurnRecord, ...] = ()
