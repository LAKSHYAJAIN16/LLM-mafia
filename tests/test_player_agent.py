from mafia_sim.agents.player_agent import PlayerAgent
from mafia_sim.game.roles import Role
from mafia_sim.game.state import GameState, Player
from mafia_sim.providers.factory import ModelSpec, build_provider

RULES = {"max_format_retries": 1, "request_timeout_seconds": 30}


def test_ask_logs_the_exact_prompt_and_raw_response():
    spec = ModelSpec(key="mock-0", display_name="mock-0", provider="mock", model_id="mock-random", vendor="mock")
    agent = PlayerAgent(spec, build_provider(spec), RULES)
    state = GameState(players=[Player(seat="Player1", model_key="mock-0", role=Role.VILLAGER)])

    reply = agent.ask(
        state,
        "system text",
        'Alive players: Player1, Player2\n{"vote": "<exact player name>"}',
        required_keys=["vote"],
        target_keys={"vote": ["Player1", "Player2"]},
        seat="Player1",
        purpose="day_vote",
    )

    assert reply["vote"] in ("Player1", "Player2")
    assert len(state.raw_calls) == 1
    call = state.raw_calls[0]
    assert call["seat"] == "Player1"
    assert call["model_key"] == "mock-0"
    assert call["purpose"] == "day_vote"
    assert call["system_prompt"] == "system text"
    assert "Alive players" in call["user_prompt"]
    assert call["response_text"]  # exact raw text the mock provider returned
    assert call["error"] is None


def test_ask_logs_every_retry_attempt_separately():
    class AlwaysMalformedProvider:
        def complete(self, system_prompt, user_prompt, temperature=0.9, max_tokens=500, timeout=60):
            from mafia_sim.providers.base import ProviderResponse

            return ProviderResponse(text="not json at all")

    spec = ModelSpec(key="broken", display_name="broken", provider="mock", model_id="x", vendor="mock")
    agent = PlayerAgent(spec, AlwaysMalformedProvider(), {"max_format_retries": 2, "request_timeout_seconds": 30})
    state = GameState(players=[Player(seat="Player1", model_key="broken", role=Role.VILLAGER)])

    agent.ask(
        state,
        "system text",
        "user text",
        required_keys=["vote"],
        target_keys={"vote": ["Player1"]},
        seat="Player1",
        purpose="day_vote",
    )

    assert len(state.raw_calls) == 3  # 1 initial attempt + 2 retries, all logged verbatim
    assert all(c["response_text"] == "not json at all" for c in state.raw_calls)
    assert state.format_failures["broken"] == 1


def test_ask_regenerates_on_third_person_self_reference_and_accepts_the_fix():
    import json

    from mafia_sim.providers.base import ProviderResponse

    class SelfReferenceThenFixedProvider:
        def __init__(self):
            self.calls = 0

        def complete(self, system_prompt, user_prompt, temperature=0.9, max_tokens=500, timeout=60):
            self.calls += 1
            if self.calls == 1:
                return ProviderResponse(text=json.dumps({"message": "Player1 thinks it's Player2."}))
            return ProviderResponse(text=json.dumps({"message": "I think it's Player2."}))

    provider = SelfReferenceThenFixedProvider()
    spec = ModelSpec(key="m", display_name="m", provider="mock", model_id="x", vendor="mock")
    agent = PlayerAgent(spec, provider, {"max_format_retries": 2, "request_timeout_seconds": 30})
    state = GameState(players=[Player(seat="Player1", model_key="m", role=Role.VILLAGER)])

    reply = agent.ask(
        state, "system text", "user text", required_keys=["message"], seat="Player1", purpose="day_discussion_open"
    )

    assert reply["message"] == "I think it's Player2."
    assert provider.calls == 2
    # The regenerate attempt's logged prompt carries the corrective note, not the bare original.
    assert "SYSTEM NOTE" in state.raw_calls[1]["user_prompt"]
    assert "Player1" in state.raw_calls[1]["user_prompt"]
    assert state.format_failures == {}  # not a format failure -- a content regenerate, tracked separately


def test_ask_accepts_the_last_attempt_even_if_self_reference_never_gets_fixed():
    from mafia_sim.providers.base import ProviderResponse

    class AlwaysSelfReferencingProvider:
        def __init__(self):
            self.calls = 0

        def complete(self, system_prompt, user_prompt, temperature=0.9, max_tokens=500, timeout=60):
            import json

            self.calls += 1
            return ProviderResponse(text=json.dumps({"message": "Player1 is suspicious of Player1."}))

    provider = AlwaysSelfReferencingProvider()
    spec = ModelSpec(key="m", display_name="m", provider="mock", model_id="x", vendor="mock")
    agent = PlayerAgent(spec, provider, {"max_format_retries": 1, "request_timeout_seconds": 30})
    state = GameState(players=[Player(seat="Player1", model_key="m", role=Role.VILLAGER)])

    reply = agent.ask(
        state, "system text", "user text", required_keys=["message"], seat="Player1", purpose="day_discussion_open"
    )

    assert reply["message"] == "Player1 is suspicious of Player1."
    assert provider.calls == 2  # 1 initial + the 1 configured retry, then gives up and accepts it
