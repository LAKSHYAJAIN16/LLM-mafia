from mafia_sim.providers.factory import ModelSpec, build_provider
from mafia_sim.providers.mock_provider import MockProvider
from mafia_sim.sim.tournament import setup_game
from mafia_sim.game.engine import GameEngine
from mafia_sim.game.roles import Role
from mafia_sim.game.state import GameState, Player

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
        spec = ModelSpec(
            key=key, display_name=key, provider="mock", model_id="mock-random", vendor=f"vendor-{i}"
        )
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


def _villagers(n: int) -> list[Player]:
    return [Player(seat=f"Player{i}", model_key="m", role=Role.VILLAGER) for i in range(1, n + 1)]


class ScriptedAgent:
    """Test double standing in for PlayerAgent: returns a scripted vote each time a
    vote is required (one entry consumed per voting round, clamped at the last entry),
    and a throwaway message otherwise (e.g. showdown defense speeches).
    """

    def __init__(self, votes: list[str]):
        self.votes = votes
        self.vote_calls = 0

    def ask(self, state, system_prompt, user_prompt, required_keys, target_keys=None, seat=None, purpose=""):
        if "vote" in required_keys:
            vote = self.votes[min(self.vote_calls, len(self.votes) - 1)]
            self.vote_calls += 1
            return {"thought": "", "vote": vote}
        return {"thought": "", "messages": ["making my case"]}


def test_showdown_resolves_a_tie_via_revote():
    state = GameState(players=_villagers(4))
    state.day = 1
    agents = {
        "Player1": ScriptedAgent(["Player3", "Player3"]),
        "Player2": ScriptedAgent(["Player3", "Player1"]),
        "Player3": ScriptedAgent(["Player1", "Player3"]),
        "Player4": ScriptedAgent(["Player1", "Player3"]),
    }
    rules = {"max_showdown_rounds": 5, "tie_vote_policy": "random", "max_format_retries": 1}
    engine = GameEngine(state, agents, rules)

    voted_out = engine._run_vote_with_showdowns()

    assert voted_out == "Player3"  # round 1 ties 2-2, round 2 breaks it 3-1
    assert len(state.day_votes) == 2
    assert any("Showdown" in e.text for e in state.public_log)
    assert len(state.vote_log) == 8  # 4 voters x 2 rounds


def test_votes_never_leak_into_the_public_transcript():
    state = GameState(players=_villagers(4))
    state.day = 1
    agents = {
        "Player1": ScriptedAgent(["Player2"]),
        "Player2": ScriptedAgent(["Player1"]),
        "Player3": ScriptedAgent(["Player1"]),
        "Player4": ScriptedAgent(["Player1"]),
    }
    rules = {"max_showdown_rounds": 5, "tie_vote_policy": "random", "max_format_retries": 1}
    engine = GameEngine(state, agents, rules)

    voted_out = engine._run_vote_with_showdowns()

    assert voted_out == "Player1"
    assert "votes for" not in state.public_transcript_text()
    assert len(state.vote_log) == 4


def test_showdown_falls_back_to_no_elimination_after_max_rounds():
    state = GameState(players=_villagers(4))
    state.day = 1
    agents = {
        "Player1": ScriptedAgent(["Player3"] * 10),
        "Player2": ScriptedAgent(["Player3"] * 10),
        "Player3": ScriptedAgent(["Player1"] * 10),
        "Player4": ScriptedAgent(["Player1"] * 10),
    }
    rules = {"max_showdown_rounds": 3, "tie_vote_policy": "no_elimination", "max_format_retries": 1}
    engine = GameEngine(state, agents, rules)

    voted_out = engine._run_vote_with_showdowns()

    assert voted_out is None
    assert len(state.day_votes) == 3


def test_summarizer_only_fires_once_a_day_ages_out_of_the_window():
    state = GameState(players=_villagers(4), transcript_full_detail_days=2)
    rules = {"request_timeout_seconds": 30}
    summarizer = MockProvider(model_id="mock-random")
    engine = GameEngine(state, agents={}, rules=rules, summarizer=summarizer, summarizer_key="mock-summarizer")

    state.day = 1
    state.log_public("day", "speech", "day1 chatter", speaker="Player1")
    engine._maybe_summarize_day(1)  # target_day = 1 - 2 = -1: too early
    assert state.day_summaries == {}

    state.day = 3
    engine._maybe_summarize_day(3)  # target_day = 3 - 2 = 1: day 1 is about to age out
    assert 1 in state.day_summaries
    assert state.day_summaries[1]
    assert len(state.raw_calls) == 1
    assert state.raw_calls[0]["purpose"] == "day_summary"
    assert state.raw_calls[0]["response_text"]
