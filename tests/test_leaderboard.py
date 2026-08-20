import json

from mafia_sim.sim.leaderboard import compute_leaderboard

GAMES = [
    {
        "game_id": "g1",
        "winner": "town",
        "days": 3,
        "players": [
            {"seat": "Player1", "model_key": "alpha", "role": "mafia", "team": "mafia",
             "alive": False, "death_day": 2, "death_cause": "lynched"},
            {"seat": "Player2", "model_key": "beta", "role": "villager", "team": "town",
             "alive": True, "death_day": None, "death_cause": None},
        ],
        "format_failures": {"alpha": 1},
    },
    {
        "game_id": "g2",
        "winner": "mafia",
        "days": 2,
        "players": [
            {"seat": "Player1", "model_key": "alpha", "role": "mafia", "team": "mafia",
             "alive": True, "death_day": None, "death_cause": None},
            {"seat": "Player2", "model_key": "beta", "role": "villager", "team": "town",
             "alive": False, "death_day": 1, "death_cause": "lynched"},
        ],
        "format_failures": {},
    },
]


def test_compute_leaderboard(tmp_path):
    path = tmp_path / "summary.jsonl"
    with open(path, "w", encoding="utf-8") as f:
        for g in GAMES:
            f.write(json.dumps(g) + "\n")

    stats = compute_leaderboard(str(path))

    alpha = stats["alpha"]
    assert alpha.games == 2
    assert alpha.games_as_mafia == 2
    assert alpha.wins_as_mafia == 1  # won g2 as mafia
    assert alpha.lynched_while_mafia == 1  # caught in g1
    assert alpha.format_failures == 1

    beta = stats["beta"]
    assert beta.games == 2
    assert beta.games_as_town == 2
    assert beta.wins_as_town == 1  # won g1 as town
    assert beta.lynched_while_town == 1  # friendly-fired in g2

    # Elo should have diverged from the 1500 starting point after two games.
    assert alpha.elo != 1500.0
    assert beta.elo != 1500.0
