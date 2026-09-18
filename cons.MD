# cons.MD — Teach-Back AI Chatbot

## 1. Project Mission

Build a **Teach-Back AI Chatbot** where the **human teaches the AI**.

This is NOT:
- a traditional AI tutor that lectures the user;
- an LMS or full learning platform;
- a quiz-first system;
- a generic RAG chatbot;
- a multi-agent system for its own sake.

The core interaction is:

```text
User teaches/explains
        ↓
Hidden Evaluator analyzes the explanation
        ↓
Update conversation learning state
        ↓
Deterministic policy chooses next action
        ↓
AI Student asks/probes/challenges
        ↓
User explains again
        ↺
```

The product succeeds when the chatbot makes the user reveal and refine their own understanding.

---

## 2. Core Product Principle

**The visible AI is a student, not a teacher.**

The AI Student should:
- ask the user to explain;
- ask natural follow-up questions;
- probe missing concepts;
- ask for clarification when reasoning is vague;
- challenge misconceptions without immediately revealing the answer;
- use examples/counterexamples when useful;
- ask one main question at a time.

The AI Student should NOT:
- lecture by default;
- dump the correct answer after every mistake;
- say what concept the user "forgot" before probing it;
- turn the session into a multiple-choice quiz;
- praise every answer mechanically;
- claim the user understands something without evidence.

A separate **hidden Evaluator** performs assessment.

---

## 3. Research/Design Inspiration

### OATutor
Learn from:
- Knowledge Components (KC): divide a topic into assessable concepts.
- Evidence/state-driven adaptation.
- Scaffolding rather than immediately giving answers.
- Interaction logging and experimentability.

Do NOT reproduce the full OATutor LMS/adaptive course system.

### PedagogicalRL
Learn from:
- multi-turn teacher/student interaction harness;
- separation between conversational actor and judge/evaluator;
- evaluation of pedagogical dialogue.

For this project, invert the roles:

```text
PedagogicalRL idea:
AI Teacher ↔ Student → Judge

Our system:
Human Teacher ↔ AI Student
                   ↓
             Hidden Evaluator
```

### ThinkCode
Learn from:
- Socratic questioning;
- conversational orchestration;
- generating guiding questions rather than immediately giving solutions.

---

## 4. Scope

### In scope for V1

1. User selects/starts a Teach-Back topic.
2. Topic has a structured ground-truth definition.
3. Chatbot asks user to teach the topic.
4. User explains in free-form natural language.
5. Hidden Evaluator detects:
   - covered concepts;
   - missing concepts;
   - misconceptions;
   - unclear concepts/claims.
6. State is updated with evidence.
7. Rule-based policy selects:
   - `PROBE`
   - `CLARIFY`
   - `CHALLENGE`
   - `FINISH`
8. AI Student creates one natural follow-up.
9. Loop continues.
10. Session ends when completion criteria are satisfied.
11. Every important step is logged for later evaluation.

### Explicitly out of scope for V1

- LMS.
- Course enrollment.
- Teacher dashboard.
- Gamification.
- Full curriculum planning.
- Long-term mastery prediction/BKT.
- Automatic grading.
- Certificates.
- Multi-agent supervisor architecture.
- Neo4j/knowledge graph infrastructure.
- Kafka/event streaming.
- Kubernetes.
- Fine-tuning models.
- Voice/video.
- Autonomous lesson generation from arbitrary internet sources.

Keep V1 focused on **Teach-Back conversation quality**.

---

## 5. System Architecture

```text
                      ┌─────────────────┐
                      │      USER       │
                      │ Human = Teacher │
                      └────────┬────────┘
                               │
                               │ explanation
                               ▼
                    ┌────────────────────┐
                    │   Chat API / UI    │
                    └─────────┬──────────┘
                              ▼
                    ┌────────────────────┐
                    │ TeachBack Service  │
                    │   Orchestrator     │
                    └─────────┬──────────┘
                              │
                ┌─────────────┴─────────────┐
                ▼                           ▼
       ┌─────────────────┐         ┌─────────────────┐
       │ Hidden Evaluator│◄────────│ Ground Truth /  │
       │       LLM       │         │ Lesson Context  │
       └────────┬────────┘         └─────────────────┘
                │
                │ structured evaluation
                ▼
       ┌─────────────────────┐
       │ Conversation State  │
       │ + Evidence          │
       └──────────┬──────────┘
                  ▼
       ┌─────────────────────┐
       │ Deterministic Policy│
       └──────────┬──────────┘
                  │
        ┌─────────┼──────────┐
        │         │          │
      PROBE    CLARIFY    CHALLENGE
        └─────────┼──────────┘
                  ▼
       ┌─────────────────────┐
       │   AI Student LLM    │
       └──────────┬──────────┘
                  │
                  ▼
                 USER
                  │
                  └──────────────↺
```

`FINISH` bypasses another probe and produces the session completion result.

---

## 6. Architectural Rule

Separate these three concerns:

### Evaluator — decides WHAT the user demonstrated

Example:

```json
{
  "covered": ["consumer_group"],
  "missing": ["partition_assignment", "offset"],
  "misconceptions": [],
  "unclear": ["group_id"],
  "evidence": []
}
```

### Policy — decides WHAT TO DO NEXT

Example:

```text
misconception exists → CHALLENGE
unclear exists        → CLARIFY
missing exists        → PROBE
all requirements met  → FINISH
```

### Student Agent — decides HOW TO SAY IT

Example:

```text
action = PROBE
target = partition_assignment

→ "Nếu một topic có 3 partition nhưng group có 5 consumer thì
   5 consumer đó sẽ chia nhau xử lý như thế nào?"
```

**Never allow one LLM call to own evaluation + state + policy + response generation.**

---

## 7. Knowledge / Lesson Format

V1 should use curated structured topic definitions.

Example:

```yaml
id: kafka_consumer_group
title: Kafka Consumer Group

concepts:
  consumer_group:
    required: true
    description: >
      Consumers cooperate as a group to consume topic partitions.

  group_id:
    required: true
    description: >
      Consumers with the same group.id belong to the same consumer group.

  partition_assignment:
    required: true
    description: >
      Within one consumer group, a partition is assigned to at most one
      consumer at a time.

  offset:
    required: true
    description: >
      An offset identifies a record position within a partition.

  rebalance:
    required: true
    description: >
      Partition ownership is redistributed when relevant group membership
      or subscription conditions change.

misconceptions:
  - id: M01
    concept: partition_assignment
    incorrect_claim: >
      Every consumer in a group receives every message.
    correction: >
      Topic partitions are distributed among consumers in the group.

  - id: M02
    concept: offset
    incorrect_claim: >
      Offset is the number of messages remaining.
    correction: >
      Offset represents a record position within a partition.
```

Do not require a vector database for this initial structured ground truth.

RAG can be added later for supporting source material.

---

## 8. State Model

Suggested V1 state:

```python
class TeachBackState(BaseModel):
    session_id: str
    topic_id: str

    covered_concepts: list[str] = []
    missing_concepts: list[str] = []
    unclear_concepts: list[str] = []
    misconceptions: list[str] = []

    evidence: list[Evidence] = []

    current_target: str | None = None
    next_action: str | None = None

    turn_count: int = 0
    status: Literal["active", "completed", "stopped"] = "active"
```

Evidence:

```python
class Evidence(BaseModel):
    concept_id: str
    user_quote: str
    judgment: Literal["correct", "incorrect", "unclear"]
    explanation: str
    confidence: float
    turn: int
```

Important:

**Do not mark a concept as covered merely because it appeared in context.  
There must be evidence from the user's own explanation.**

---

## 9. Evaluator Contract

The Evaluator is hidden from the user.

Inputs:
- structured topic ground truth;
- required concepts;
- known misconceptions;
- current state;
- recent conversation;
- latest user message.

Output MUST be structured.

Suggested schema:

```python
class EvaluationResult(BaseModel):
    covered: list[str]
    missing: list[str]
    misconceptions: list[str]
    unclear: list[str]
    evidence: list[Evidence]
    recommended_target: str | None
    confidence: float
```

Evaluator rules:

1. Evaluate only what the user demonstrates.
2. Do not infer understanding from vocabulary alone.
3. Do not penalize wording differences when the meaning is correct.
4. Distinguish:
   - missing = user did not demonstrate it;
   - unclear = user attempted it but meaning is ambiguous;
   - misconception = user expressed a materially incorrect belief.
5. Prefer evidence from the latest answer but use dialogue context where necessary.
6. Attach a supporting user quote/span for important judgments.
7. Never talk directly to the user.
8. Never generate the next conversational response.
9. Do not invent new required concepts outside the topic definition unless flagged separately as optional observation.

---

## 10. Policy Engine

V1 policy should be deterministic and testable.

Initial priority:

```python
def choose_action(state: TeachBackState) -> Action:
    if state.misconceptions:
        return Action.CHALLENGE

    if state.unclear_concepts:
        return Action.CLARIFY

    if state.missing_concepts:
        return Action.PROBE

    return Action.FINISH
```

Improve target selection separately.

Possible target priority:

```text
1. unresolved misconception
2. unclear required concept
3. missing prerequisite/central concept
4. other missing required concept
5. finish
```

Avoid making target selection random unless experimentation explicitly requires it.

---

## 11. AI Student Contract

The visible chatbot is a curious student.

Inputs:
- selected action;
- target concept;
- relevant evaluation;
- conversation context;
- optional misconception;
- persona configuration.

Output:
- one concise, natural response;
- normally one main question.

### PROBE

Goal: make the user demonstrate a missing concept without naming the answer.

Bad:

> You forgot partition assignment. Explain partition assignment.

Better:

> Nếu trong group có nhiều consumer thì Kafka quyết định consumer nào xử lý partition nào vậy?

### CLARIFY

Goal: resolve ambiguous reasoning.

> Chỗ bạn nói "Kafka tự nhớ vị trí" nghĩa là vị trí đó được lưu theo cái gì?

### CHALLENGE

Goal: make the user reconsider a misconception without immediately correcting them.

User:

> Offset là số message còn lại.

Student:

> Nhưng nếu producer cứ thêm message mới thì số message còn lại thay đổi liên tục. Vậy consumer dùng nó để biết chính xác mình đã đọc tới đâu như thế nào?

### FINISH

Do not ask another question.

Return a compact completion response based on verified state.

---

## 12. Conversation Example

```text
AI Student:
Mình chưa hiểu Consumer Group lắm. Bạn thử giải thích cho mình được không?

User:
Consumer group là nhiều consumer cùng xử lý dữ liệu của một topic.

[Evaluator]
covered: consumer_group
missing: group_id, partition_assignment, offset, rebalance

[Policy]
PROBE → partition_assignment

AI Student:
Vậy nếu trong group có nhiều consumer thì chúng chia nhau dữ liệu kiểu gì?

User:
Mỗi partition sẽ được giao cho một consumer.

[Evaluator]
covered += partition_assignment

[Policy]
PROBE → offset

AI Student:
Nếu consumer đang xử lý rồi bị restart thì nó biết lần trước mình đọc đến đâu bằng cách nào?

User:
Offset chắc là số message còn lại.

[Evaluator]
misconception: M02

[Policy]
CHALLENGE → M02

AI Student:
Nhưng nếu producer liên tục thêm message thì số message còn lại thay đổi suốt. Vậy giá trị đó làm sao chỉ chính xác nơi consumer đã đọc tới?

User:
À, vậy offset phải là vị trí của record trong partition...

[Evaluator]
M02 resolved
offset covered

...
```

Internal evaluator/policy outputs are never shown directly in the normal chat UI.

---

## 13. Suggested V1 Stack

Prefer a small modular monolith.

```text
Frontend
  Next.js / React
       │
       ▼
Backend
  FastAPI
       │
       ▼
TeachBack Orchestrator
  ├── Evaluator
  ├── Policy
  └── Student Generator
       │
       ▼
LLM Provider
       │
       ▼
PostgreSQL
```

Optional later:
- `pgvector` for RAG;
- Redis for cache/temporary state;
- LangGraph when graph complexity actually warrants it.

Do NOT add infrastructure without a concrete need.

---

## 14. Suggested Repository Layout

```text
teachback-ai/
├── README.md
├── cons.MD
├── pyproject.toml
│
├── app/
│   ├── main.py
│   │
│   ├── api/
│   │   ├── sessions.py
│   │   └── messages.py
│   │
│   ├── teachback/
│   │   ├── orchestrator.py
│   │   ├── evaluator.py
│   │   ├── policy.py
│   │   ├── student.py
│   │   ├── state.py
│   │   └── schemas.py
│   │
│   ├── knowledge/
│   │   ├── loader.py
│   │   └── schemas.py
│   │
│   ├── llm/
│   │   ├── client.py
│   │   └── structured.py
│   │
│   ├── prompts/
│   │   ├── evaluator.md
│   │   └── student.md
│   │
│   └── db/
│       ├── models.py
│       └── repository.py
│
├── knowledge/
│   └── kafka_consumer_group.yaml
│
├── evals/
│   ├── dataset.yaml
│   ├── runner.py
│   ├── metrics.py
│   └── reports/
│
└── tests/
    ├── unit/
    │   ├── test_policy.py
    │   ├── test_state.py
    │   └── test_knowledge.py
    └── integration/
        └── test_teachback_flow.py
```

---

## 15. API Shape

Minimal endpoints:

```text
POST /topics/{topic_id}/sessions
POST /sessions/{session_id}/messages
GET  /sessions/{session_id}
POST /sessions/{session_id}/stop
```

Start session response may include the AI Student's opening question.

Message endpoint flow:

```text
load session
→ evaluate latest user answer
→ update state/evidence
→ choose action
→ generate student response or finish
→ persist
→ return response
```

---

## 16. Persistence

Minimum entities:

```text
topics
sessions
messages
evaluations
evidence
```

Suggested session fields:

```text
id
topic_id
state_json
status
turn_count
created_at
updated_at
```

Messages:

```text
id
session_id
role
content
turn_number
created_at
```

Evaluations:

```text
id
session_id
turn_number
model
prompt_version
result_json
latency_ms
created_at
```

Always preserve raw structured evaluation results for debugging/evals.

---

## 17. Observability

Every turn should record:

```json
{
  "session_id": "...",
  "turn": 4,
  "topic_id": "...",
  "target_concept": "offset",
  "evaluation": {},
  "policy_action": "challenge",
  "student_response": "...",
  "evaluator_model": "...",
  "student_model": "...",
  "evaluator_prompt_version": "v1",
  "student_prompt_version": "v1",
  "latency_ms": {}
}
```

Do not log secrets/API keys.

Make model and prompt versions explicit so regressions can be traced.

---

## 18. Eval Harness — First-Class Requirement

Do not treat evals as a future task.

Maintain a regression dataset from the beginning.

Example:

```yaml
- id: offset_misconception_001

  topic: kafka_consumer_group

  user_message: >
    Offset là số lượng message chưa đọc.

  expected:
    misconception:
      - M02
    action: CHALLENGE

  forbidden:
    covered:
      - offset
    action:
      - FINISH
```

Test categories:

```text
correct explanation
missing concept
partial explanation
ambiguous explanation
known misconception
novel misconception
self-correction
user asks AI for the answer
off-topic response
very short answer
conflicting statements across turns
```

At minimum measure:

```text
concept detection precision/recall
misconception detection precision/recall
policy action accuracy
false completion rate
state consistency
challenge quality
answer leakage rate
```

A critical metric is **false completion rate**:
the system must not end a Teach-Back session while important required concepts or unresolved misconceptions remain.

---

## 19. Testing Priorities

### Unit tests

Deterministic code:
- policy;
- state transitions;
- target selection;
- topic parsing;
- completion conditions.

### Evaluator tests

Use fixed cases where expected concept/misconception labels are known.

### End-to-end scenario tests

Example:

```text
start
→ partial explanation
→ probe
→ misconception
→ challenge
→ self-correction
→ remaining concept
→ probe
→ completion
```

Assert state after every turn.

---

## 20. Prompt Versioning

Prompts are production code.

Keep them in files and version them.

```text
prompts/
├── evaluator_v1.md
├── evaluator_v2.md
├── student_v1.md
└── student_v2.md
```

Never make silent prompt changes.

Any important prompt/model change should be run against the regression eval set before adoption.

---

## 21. Development Principles for Codex

When implementing this repository:

1. Read this file before making architectural changes.
2. Preserve the central separation:
   `Evaluator → State → Policy → Student`.
3. Prefer simple deterministic code over adding another agent.
4. Do not introduce an LMS or generic learning platform.
5. Do not turn the product into an AI teacher.
6. Do not introduce LangGraph merely because this is an AI application.
7. Keep LLM calls behind interfaces so providers/models can change.
8. Require typed/validated structured evaluator output.
9. Keep business/state logic independent from prompts.
10. Add tests for every policy/state behavior.
11. Every discovered production failure should become an eval case.
12. Do not hide fallback behavior; log it.
13. Do not silently modify knowledge ground truth.
14. Optimize for traceability and testability before cleverness.
15. Make small, reviewable changes.

---

## 22. Implementation Order

### Phase 0 — Bootstrap
- FastAPI project.
- config/environment.
- topic YAML loader.
- Pydantic schemas.
- tests.

### Phase 1 — Deterministic skeleton
Implement without real LLM:
- session state;
- policy;
- state transitions;
- fake evaluator;
- fake student response;
- API.

Goal: prove orchestration.

### Phase 2 — Evaluator
- real LLM client;
- structured output;
- evidence extraction;
- evaluation persistence;
- evaluator regression dataset.

Goal: reliable detection of covered/missing/wrong/unclear.

### Phase 3 — AI Student
- Socratic student prompt;
- `PROBE`;
- `CLARIFY`;
- `CHALLENGE`;
- answer-leakage tests.

Goal: natural Teach-Back dialogue.

### Phase 4 — Full session
- opening turn;
- repeated multi-turn interaction;
- misconception resolution;
- completion criteria;
- final compact summary.

### Phase 5 — Eval/observability
- batch eval runner;
- metrics;
- prompt/model comparison;
- latency/token/cost logging.

### Phase 6 — RAG only if needed
Add retrieval when structured lesson ground truth is insufficient.

Do not add RAG before there is an observed need.

---

## 23. Definition of Done for V1

V1 is ready when:

- a user can start a topic;
- the AI asks the user to teach it;
- user explanations are evaluated into structured evidence;
- concepts are tracked across turns;
- known misconceptions are detected;
- the policy chooses appropriate probe/clarify/challenge actions;
- AI Student does not immediately reveal answers;
- corrected misconceptions can be resolved;
- completion only occurs after required concepts are demonstrated;
- sessions and internal evaluations are persisted;
- regression evals run automatically;
- prompts/models are versioned in logs;
- the core flow has integration tests.

---

## 24. Non-Negotiable Product Invariant

At every design decision, ask:

> **Does this make the human explain, reason, notice gaps, and teach more clearly?**

If a feature primarily makes the AI explain more, it is probably outside the core Teach-Back design.

Canonical loop:

```text
USER TEACHES
     ↓
EVALUATE EVIDENCE
     ↓
UPDATE STATE
     ↓
SELECT TARGET
     ↓
AI STUDENT ASKS
     ↓
USER TEACHES AGAIN
     ↺
```

Keep this loop small, observable, testable, and difficult for the LLM to bypass.
