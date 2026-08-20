from mafia_sim.providers.factory import ModelSpec, build_provider
from mafia_sim.sim.tournament import setup_game
from mafia_sim.game.engine import GameEngine

ROLE_SETUPS = {8: {"mafia": 2, "detective": 1, "doctor": 1}}
RULES = {
    "temperature": 0.9,
    "max_tokens": 300,
    "max_format_retries": 1,
    "request_timeout_seconds": 30,
    "max_days": 20,
    "discussion_rounds_per_day": 1,
    "reveal_role_on_death": False,
    "tie_vote_policy": "random",
}


def _mock_roster(n: int):
    roster = {}
    for i in range(n):
        key = f"mock-{i}"
        spec = ModelSpec(key=key, display_name=key, provider="mock", model_id="mock-random")
        roster[key] = (spec, build_provider(spec))
    return roster


def test_full_game_terminates_with_a_result():
    roster = _mock_roster(8)
    state, agents = setup_game(roster, player_count=8, role_setups=ROLE_SETUPS, rules=RULES)
    assert len(state.players) == 8

    engine = GameEngine(state, agents, RULES)
    result = engine.run()

    assert result.winner in ("mafia", "town", None)
    assert result.days <= RULES["max_days"]
    assert len(result.state.players) == 8


def test_role_counts_match_config():
    roster = _mock_roster(8)
    state, _ = setup_game(roster, player_count=8, role_setups=ROLE_SETUPS, rules=RULES)
    roles = [p.role.value for p in state.players]
    assert roles.count("mafia") == 2
    assert roles.count("detective") == 1
    assert roles.count("doctor") == 1
    assert roles.count("villager") == 4
