from mafia_sim.sim.deception_matrix import compute_deception_matrix, render_markdown_table


def _player(seat, model_key, role, death_day=None):
    return {"seat": seat, "model_key": model_key, "role": role, "death_day": death_day}


def test_records_opportunities_and_catches_for_non_mafia_voters():
    game = {
        "players": [
            _player("Player1", "model-a", "villager"),
            _player("Player2", "model-b", "detective"),
            _player("Player3", "model-c", "mafia"),
        ],
        "day_votes": [
            {"day": 1, "round": 1, "votes": {"Player1": "Player3", "Player2": "Player1"}},
        ],
    }

    matrix = compute_deception_matrix([game])

    # Player1 (model-a) voted for the mafia player (model-c) -- a catch.
    assert matrix[("model-a", "model-c")] == {"opportunities": 1, "catches": 1}
    # Player2 (model-b) had the same opportunity but voted elsewhere -- a miss.
    assert matrix[("model-b", "model-c")] == {"opportunities": 1, "catches": 0}


def test_mafia_voting_mafia_is_not_counted_as_an_accusation():
    game = {
        "players": [
            _player("Player1", "model-a", "mafia"),
            _player("Player2", "model-b", "mafia"),
        ],
        "day_votes": [{"day": 1, "round": 1, "votes": {"Player1": "Player2"}}],
    }

    matrix = compute_deception_matrix([game])

    assert matrix == {}


def test_dead_mafia_from_an_earlier_day_is_not_a_later_opportunity():
    game = {
        "players": [
            _player("Player1", "model-a", "villager"),
            _player("Player2", "model-b", "mafia", death_day=1),  # eliminated day 1
        ],
        "day_votes": [
            {"day": 1, "round": 1, "votes": {"Player1": "Player2"}},  # legit opportunity, caught
            {"day": 2, "round": 1, "votes": {"Player1": "Player2"}},  # Player2 already dead -- not a real opportunity
        ],
    }

    matrix = compute_deception_matrix([game])

    assert matrix[("model-a", "model-b")] == {"opportunities": 1, "catches": 1}


def test_aggregates_across_multiple_games():
    game1 = {
        "players": [_player("Player1", "model-a", "villager"), _player("Player2", "model-b", "mafia")],
        "day_votes": [{"day": 1, "round": 1, "votes": {"Player1": "Player2"}}],
    }
    game2 = {
        "players": [_player("Player1", "model-a", "villager"), _player("Player2", "model-b", "mafia")],
        "day_votes": [{"day": 1, "round": 1, "votes": {"Player1": "Player1"}}],  # nonsense target, just a miss
    }

    matrix = compute_deception_matrix([game1, game2])

    assert matrix[("model-a", "model-b")] == {"opportunities": 2, "catches": 1}


def test_render_markdown_table_filters_by_min_opportunities_and_reports_no_data():
    matrix = {
        ("model-a", "model-c"): {"opportunities": 5, "catches": 3},
        ("model-b", "model-c"): {"opportunities": 1, "catches": 0},
    }

    full = render_markdown_table(matrix, min_opportunities=1)
    assert "model-a" in full and "model-b" in full
    assert "60%" in full  # 3/5

    filtered = render_markdown_table(matrix, min_opportunities=3)
    assert "model-a" in filtered
    assert "model-b" not in filtered  # only 1 opportunity, below the threshold

    assert "run more games" in render_markdown_table({}, min_opportunities=1)
