import pytest

from mafia_sim.game.roles import Role, build_role_setup

ROLE_SETUPS = {
    5: {"mafia": 1, "detective": 1, "doctor": 0},
    8: {"mafia": 2, "detective": 1, "doctor": 1},
}


def test_build_role_setup_exact_match():
    counts = build_role_setup(8, ROLE_SETUPS)
    assert counts[Role.MAFIA] == 2
    assert counts[Role.DETECTIVE] == 1
    assert counts[Role.DOCTOR] == 1
    assert counts[Role.VILLAGER] == 4
    assert sum(counts.values()) == 8


def test_build_role_setup_falls_back_to_closest_smaller():
    counts = build_role_setup(10, ROLE_SETUPS)
    assert counts[Role.MAFIA] == 2
    assert sum(counts.values()) == 10


def test_build_role_setup_no_smaller_entry_raises():
    with pytest.raises(ValueError):
        build_role_setup(3, ROLE_SETUPS)
