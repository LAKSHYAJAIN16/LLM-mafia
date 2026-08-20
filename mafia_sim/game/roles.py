from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    MAFIA = "mafia"
    DETECTIVE = "detective"
    DOCTOR = "doctor"
    VILLAGER = "villager"

    @property
    def team(self) -> str:
        return "mafia" if self == Role.MAFIA else "town"


def build_role_setup(player_count: int, role_setups: dict[int, dict]) -> dict[Role, int]:
    """Picks the role_setups entry for player_count, or the closest smaller one,
    and fills the remainder with villagers.
    """
    available = sorted(k for k in role_setups if k <= player_count)
    if not available:
        raise ValueError(f"no role_setups entry <= {player_count} players")
    chosen = role_setups[available[-1]]

    mafia = chosen.get("mafia", 0)
    detective = chosen.get("detective", 0)
    doctor = chosen.get("doctor", 0)
    special_total = mafia + detective + doctor
    if special_total > player_count:
        raise ValueError(f"role_setups for {available[-1]} players needs {special_total} slots")
    villagers = player_count - special_total

    return {
        Role.MAFIA: mafia,
        Role.DETECTIVE: detective,
        Role.DOCTOR: doctor,
        Role.VILLAGER: villagers,
    }
