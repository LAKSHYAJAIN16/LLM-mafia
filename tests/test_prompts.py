from mafia_sim.game import prompts
from mafia_sim.game.roles import Role
from mafia_sim.game.state import GameState, Player


def test_system_prompt_warns_against_third_person_self_reference_and_repetition():
    players = [Player(seat="Player1", model_key="m", role=Role.VILLAGER)]
    state = GameState(players=players)

    text = prompts.build_system_prompt(state, players[0])

    assert "never your own" in text and "seat name in the third person" in text
    assert "Never repeat something you've already said" in text


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


def test_mafia_system_prompt_includes_their_own_night_chat_history():
    players = [
        Player(seat="Player1", model_key="m", role=Role.MAFIA),
        Player(seat="Player2", model_key="m", role=Role.MAFIA),
        Player(seat="Player3", model_key="m", role=Role.VILLAGER),
    ]
    state = GameState(players=players)
    state.day = 1
    state.log_mafia("mafia_chat", "Let's go with Player3, low risk pick.", speaker="Player1")

    mafia_text = prompts.build_system_prompt(state, players[0])
    villager_text = prompts.build_system_prompt(state, players[2])

    # Mafia remembers their own team's decision -- shouldn't have to roleplay
    # confusion about why the night kill happened, since they were part of it.
    assert "Let's go with Player3, low risk pick." in mafia_text
    assert "private mafia team chat" in mafia_text
    # But it never leaks to a non-mafia player's own prompt.
    assert "Let's go with Player3, low risk pick." not in villager_text


def test_mafia_system_prompt_omits_chat_section_before_any_night_has_happened():
    players = [
        Player(seat="Player1", model_key="m", role=Role.MAFIA),
        Player(seat="Player2", model_key="m", role=Role.MAFIA),
    ]
    state = GameState(players=players)

    text = prompts.build_system_prompt(state, players[0])

    assert "private mafia team chat" not in text
