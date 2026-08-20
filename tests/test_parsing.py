from mafia_sim.game.parsing import parse_json_object, resolve_seat


def test_parse_plain_json():
    obj = parse_json_object('{"thought": "hi", "vote": "Player2"}')
    assert obj == {"thought": "hi", "vote": "Player2"}


def test_parse_json_with_surrounding_text():
    text = 'Sure, here you go:\n```json\n{"message": "hello", "target": "Player1"}\n```\nHope that helps!'
    obj = parse_json_object(text)
    assert obj == {"message": "hello", "target": "Player1"}


def test_parse_invalid_json_returns_none():
    assert parse_json_object("not json at all") is None
    assert parse_json_object("") is None


def test_resolve_seat_exact():
    assert resolve_seat("Player3", ["Player1", "Player2", "Player3"]) == "Player3"


def test_resolve_seat_fuzzy():
    candidates = ["Player1", "Player2", "Player3"]
    assert resolve_seat("player 3", candidates) == "Player3"
    assert resolve_seat("PLAYER_2.", candidates) == "Player2"


def test_resolve_seat_unknown():
    assert resolve_seat("Nobody", ["Player1", "Player2"]) is None
