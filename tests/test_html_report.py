from mafia_sim.sim.html_report import render_game_html


def _minimal_record(**overrides) -> dict:
    record = {
        "game_id": "game_0000_test",
        "winner": "town",
        "days": 3,
        "total_cost_usd": 0.1803,
        "players": [
            {
                "seat": "Player1",
                "model_key": "mock-0",
                "role": "villager",
                "alive": True,
                "death_day": None,
                "death_cause": None,
            }
        ],
        "public_log": [],
        "mafia_log": [],
        "thought_log": [],
        "vote_log": [],
        "day_summaries": {},
    }
    record.update(overrides)
    return record


def test_render_game_html_shows_the_total_cost():
    html = render_game_html(_minimal_record())
    assert "$0.1803" in html


def test_render_game_html_shows_zero_cost_when_missing():
    record = _minimal_record()
    del record["total_cost_usd"]
    html = render_game_html(record)
    assert "$0.0000" in html
