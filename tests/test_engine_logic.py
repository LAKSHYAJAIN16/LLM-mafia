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


class _FixedNightAgent:
    """Test double: always proposes/saves/investigates a fixed seat, regardless of
    prompt content -- used to drive _run_night deterministically.
    """

    def __init__(self, value: str):
        self.value = value

    def ask(self, state, system_prompt, user_prompt, required_keys, target_keys=None, seat=None, purpose=""):
        reply = {"thought": "", "messages": ["ok"]}
        for key in ("target", "save", "investigate"):
            if key in required_keys:
                reply[key] = self.value
        return reply


def test_doctor_gets_private_feedback_when_a_save_blocks_an_attack():
    players = [
        Player(seat="Player1", model_key="m", role=Role.MAFIA),
        Player(seat="Player2", model_key="m", role=Role.DOCTOR),
        Player(seat="Player3", model_key="m", role=Role.VILLAGER),
    ]
    state = GameState(players=players)
    state.day = 1
    agents = {
        "Player1": _FixedNightAgent("Player3"),  # mafia targets Player3
        "Player2": _FixedNightAgent("Player3"),  # doctor protects Player3 -- blocks it
    }
    rules = {"max_format_retries": 1, "reveal_role_on_death": False}
    engine = GameEngine(state, agents, rules)

    engine._run_night()

    assert state.get("Player3").alive is True
    doctor = state.get("Player2")
    assert any("saved them" in n for n in doctor.private_notes)
    assert any("No one died" in e.text for e in state.public_log)


def test_doctor_gets_private_feedback_when_the_save_was_not_needed():
    players = [
        Player(seat="Player1", model_key="m", role=Role.MAFIA),
        Player(seat="Player2", model_key="m", role=Role.DOCTOR),
        Player(seat="Player3", model_key="m", role=Role.VILLAGER),
    ]
    state = GameState(players=players)
    state.day = 1
    agents = {
        "Player1": _FixedNightAgent("Player3"),  # mafia targets Player3
        "Player2": _FixedNightAgent("Player2"),  # doctor protects themselves instead
    }
    rules = {"max_format_retries": 1, "reveal_role_on_death": False}
    engine = GameEngine(state, agents, rules)

    engine._run_night()

    assert state.get("Player3").alive is False
    doctor = state.get("Player2")
    assert any("No attack landed" in n for n in doctor.private_notes)


class ScriptedDiscussionAgent:
    """Test double for day discussion: always speaks (with a fixed message) when
    chosen as the forced opener, and returns a fixed action/message on every poll
    otherwise -- used to drive _run_discussion deterministically.
    """

    def __init__(self, action: str = "pass", message: str = "hi"):
        self.action = action
        self.message = message

    def ask(self, state, system_prompt, user_prompt, required_keys, target_keys=None, seat=None, purpose=""):
        if purpose == "day_discussion_open":
            return {"thought": "", "message": self.message}
        return {"thought": "", "action": self.action, "message": self.message}


def test_discussion_opener_is_forced_to_speak_even_if_configured_to_pass():
    state = GameState(players=_villagers(1))
    agents = {"Player1": ScriptedDiscussionAgent(action="pass", message="opening line")}
    rules = {"max_format_retries": 1, "max_discussion_polls_per_day": 100}
    engine = GameEngine(state, agents, rules)

    engine._run_discussion()

    speeches = [e for e in state.public_log if e.kind == "speech"]
    assert len(speeches) == 1
    assert speeches[0].text == "opening line"


def test_discussion_ends_as_soon_as_everyone_passes():
    state = GameState(players=_villagers(3))
    agents = {p.seat: ScriptedDiscussionAgent(action="pass") for p in state.players}
    rules = {"max_format_retries": 1, "max_discussion_polls_per_day": 100}
    engine = GameEngine(state, agents, rules)

    engine._run_discussion()

    speeches = [e for e in state.public_log if e.kind == "speech"]
    assert len(speeches) == 1  # only the forced opener; nobody else ever chose to speak


def test_discussion_caps_a_talkative_player_at_three_messages_per_day():
    state = GameState(players=_villagers(2))
    agents = {
        "Player1": ScriptedDiscussionAgent(action="speak", message="P1 talking"),
        "Player2": ScriptedDiscussionAgent(action="pass"),
    }
    rules = {"max_format_retries": 1, "max_discussion_polls_per_day": 100}
    engine = GameEngine(state, agents, rules)

    engine._run_discussion()

    p1_speeches = [e for e in state.public_log if e.speaker == "Player1"]
    p2_speeches = [e for e in state.public_log if e.speaker == "Player2"]
    assert len(p1_speeches) == 3  # hit the daily cap, never more
    assert len(p2_speeches) <= 1  # only ever spoke if it happened to be the forced opener


def test_discussion_treats_speak_with_no_message_as_a_pass():
    state = GameState(players=_villagers(2))
    agents = {
        "Player1": ScriptedDiscussionAgent(action="pass"),
        "Player2": ScriptedDiscussionAgent(action="speak", message=""),  # says speak but writes nothing
    }
    rules = {"max_format_retries": 1, "max_discussion_polls_per_day": 100}
    engine = GameEngine(state, agents, rules)

    engine._run_discussion()

    # Only the forced opener ever posts: Player1 always passes, and Player2's
    # "speak" with an empty message never burns budget or posts anything on a poll.
    speeches = [e for e in state.public_log if e.kind == "speech"]
    assert len(speeches) == 1


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
