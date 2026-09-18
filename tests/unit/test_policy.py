from app.teachback.models import Action, TeachBackState, TopicDefinition
from app.teachback.policy import PolicyEngine


def make_state(topic: TopicDefinition, **updates: object) -> TeachBackState:
    state = TeachBackState(session_id="session", topic_id=topic.id, topic_version=topic.version)
    return state.model_copy(update=updates)


def test_policy_priority_is_challenge_clarify_probe_finish(topic: TopicDefinition) -> None:
    policy = PolicyEngine()
    almost_complete = topic.required_concept_ids - {"group_id"}

    state = make_state(
        topic,
        covered_concepts=frozenset(almost_complete),
        unclear_concepts=frozenset({"group_id"}),
        active_misconceptions=frozenset({"M02"}),
    )
    assert policy.choose(topic, state).action is Action.CHALLENGE

    state = state.model_copy(update={"active_misconceptions": frozenset()})
    assert policy.choose(topic, state).action is Action.CLARIFY

    state = state.model_copy(update={"unclear_concepts": frozenset()})
    assert policy.choose(topic, state).action is Action.PROBE

    state = state.model_copy(update={"covered_concepts": topic.required_concept_ids})
    decision = policy.choose(topic, state)
    assert decision.action is Action.FINISH
    assert decision.target is None


def test_target_selection_uses_priority_then_declaration_order(topic: TopicDefinition) -> None:
    policy = PolicyEngine()
    state = make_state(topic)

    decision = policy.choose(topic, state)

    assert decision.action is Action.PROBE
    assert decision.target is not None
    assert decision.target.id == "consumer_group"


def test_finish_blocked_by_each_incomplete_condition(topic: TopicDefinition) -> None:
    policy = PolicyEngine()
    complete = make_state(topic, covered_concepts=topic.required_concept_ids)
    assert policy.choose(topic, complete).action is Action.FINISH

    missing = complete.model_copy(
        update={"covered_concepts": topic.required_concept_ids - {"offset"}}
    )
    assert policy.choose(topic, missing).action is Action.PROBE

    unclear = complete.model_copy(update={"unclear_concepts": frozenset({"offset"})})
    assert policy.choose(topic, unclear).action is Action.CLARIFY

    misconception = complete.model_copy(update={"active_misconceptions": frozenset({"M02"})})
    assert policy.choose(topic, misconception).action is Action.CHALLENGE
