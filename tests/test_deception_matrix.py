from mafia_sim.sim.deception_matrix import (
    aggregate_by_deceiver,
    compute_deception_matrix,
    hint_table,
    render_aggregate_table,
    render_markdown_table,
    wilson_interval,
)


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


def test_wilson_interval_zero_opportunities_returns_zero_zero():
    assert wilson_interval(0, 0) == (0.0, 0.0)


def test_wilson_interval_bounds_stay_within_zero_and_one():
    lo, hi = wilson_interval(3, 5)
    assert 0.0 <= lo <= hi <= 1.0


def test_wilson_interval_widens_as_opportunities_shrink_for_the_same_rate():
    lo_small, hi_small = wilson_interval(1, 2)  # 50% on n=2
    lo_large, hi_large = wilson_interval(50, 100)  # 50% on n=100
    assert (hi_small - lo_small) > (hi_large - lo_large)


def test_wilson_interval_perfect_rate_on_a_small_sample_still_has_a_lower_bound_below_100pct():
    lo, hi = wilson_interval(5, 5)
    assert hi == 1.0
    assert lo > 0.0  # 5/5 shouldn't be read as a confident 100% floor


def test_hint_table_filters_by_min_opportunities_and_converts_to_rate_n_tuples():
    matrix = {
        ("model-a", "model-c"): {"opportunities": 8, "catches": 2},
        ("model-b", "model-c"): {"opportunities": 2, "catches": 1},
    }

    hints = hint_table(matrix, min_opportunities=5)

    assert hints == {("model-a", "model-c"): (0.25, 8)}


def test_aggregate_by_deceiver_sums_across_all_accusers():
    matrix = {
        ("model-a", "model-x"): {"opportunities": 10, "catches": 2},
        ("model-b", "model-x"): {"opportunities": 10, "catches": 3},
        ("model-a", "model-y"): {"opportunities": 5, "catches": 5},
    }

    agg = aggregate_by_deceiver(matrix)

    assert agg["model-x"]["opportunities"] == 20
    assert agg["model-x"]["catches"] == 5
    assert agg["model-x"]["rate"] == 0.25
    assert agg["model-y"]["rate"] == 1.0


def test_render_markdown_table_includes_confidence_interval_brackets():
    matrix = {("model-a", "model-c"): {"opportunities": 5, "catches": 3}}

    text = render_markdown_table(matrix, min_opportunities=1)

    assert "60%" in text
    assert "[" in text and "%]" in text


def test_render_aggregate_table_reports_per_deceiver_summary_and_handles_empty():
    matrix = {("model-a", "model-x"): {"opportunities": 10, "catches": 5}}

    text = render_aggregate_table(matrix)

    assert "model-x" in text
    assert "50%" in text
    assert "run more games" in render_aggregate_table({}).lower()
