from mafia_sim.game import prompts
from mafia_sim.game.roles import Role
from mafia_sim.game.state import GameState, Player


def test_mafia_system_prompt_only_lists_alive_teammates_as_surviving():
    players = [
        Player(seat="Player1", model_key="m", role=Role.MAFIA),
        Player(seat="Player2", model_key="m", role=Role.MAFIA, alive=False, death_day=1, death_cause="voted_out"),
        Player(seat="Player3", model_key="m", role=Role.VILLAGER),
    ]
    state = GameState(players=players)

    text = prompts.build_system_prompt(state, players[0])

    assert "You have no surviving mafia teammates" in text
    assert "already died: Player2" in text


def test_mafia_system_prompt_lists_alive_teammate_when_present():
    players = [
        Player(seat="Player1", model_key="m", role=Role.MAFIA),
        Player(seat="Player2", model_key="m", role=Role.MAFIA),
    ]
    state = GameState(players=players)

    text = prompts.build_system_prompt(state, players[0])

    assert "surviving mafia teammate(s): Player2" in text
    assert "already died" not in text
