from mafia_sim.game.roles import Role
from mafia_sim.game.state import GameState, Player


def _state(day: int, full_detail_days: int) -> GameState:
    state = GameState(
        players=[Player(seat="Player1", model_key="m", role=Role.VILLAGER)],
        transcript_full_detail_days=full_detail_days,
    )
    state.day = day
    return state


def test_old_speech_dropped_but_system_kept():
    state = _state(day=5, full_detail_days=2)
    state.public_log = []
    state.day = 1
    state.log_public("day", "system", "Game begins.")
    state.log_public("day", "speech", "old chatter", speaker="Player1")
    state.day = 5
    state.log_public("day", "speech", "recent chatter", speaker="Player1")

    text = state.public_transcript_text()

    assert "Game begins." in text  # system events never dropped
    assert "recent chatter" in text  # within the detail window
    assert "old chatter" not in text  # speech older than the window is dropped


def test_votes_are_secret_from_players_but_kept_for_spectators():
    state = _state(day=1, full_detail_days=3)
    state.log_vote("day", "Player1", "Player1 votes for Player2")

    assert "Player1 votes for Player2" not in state.public_transcript_text()
    assert len(state.vote_log) == 1
    assert state.vote_log[0].text == "Player1 votes for Player2"


def test_all_speech_kept_within_detail_window():
    state = _state(day=2, full_detail_days=3)
    state.day = 1
    state.log_public("day", "speech", "still relevant", speaker="Player1")
    state.day = 2

    text = state.public_transcript_text()
    assert "still relevant" in text


def test_log_raw_call_records_exact_input_and_output():
    state = _state(day=1, full_detail_days=3)
    state.log_raw_call(
        seat="Player1",
        model_key="mock-0",
        purpose="day_vote",
        attempt=1,
        system_prompt="sys text",
        user_prompt="user text",
        response_text='{"vote": "Player2"}',
        error=None,
        cost_usd=0.001,
    )

    assert len(state.raw_calls) == 1
    call = state.raw_calls[0]
    assert call["system_prompt"] == "sys text"
    assert call["user_prompt"] == "user text"
    assert call["response_text"] == '{"vote": "Player2"}'
    assert call["seat"] == "Player1"
    assert call["purpose"] == "day_vote"
