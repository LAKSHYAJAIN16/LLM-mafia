from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass
class ModelStats:
    model_key: str
    games: int = 0
    wins: int = 0
    games_as_mafia: int = 0
    wins_as_mafia: int = 0
    games_as_town: int = 0
    wins_as_town: int = 0
    voted_out_while_mafia: int = 0  # town correctly caught them
    voted_out_while_town: int = 0  # town mistakenly voted out one of their own
    survival_day_fraction_sum: float = 0.0  # sum of (days survived / total game days)
    format_failures: int = 0
    total_cost_usd: float = 0.0
    elo: float = 1500.0

    @property
    def win_rate(self) -> float:
        return self.wins / self.games if self.games else 0.0

    @property
    def mafia_win_rate(self) -> float:
        return self.wins_as_mafia / self.games_as_mafia if self.games_as_mafia else 0.0

    @property
    def town_win_rate(self) -> float:
        return self.wins_as_town / self.games_as_town if self.games_as_town else 0.0

    @property
    def avg_survival_fraction(self) -> float:
        return self.survival_day_fraction_sum / self.games if self.games else 0.0

    @property
    def detection_rate_against(self) -> float:
        """How often this model got voted out while playing mafia (higher = easier to catch)."""
        return self.voted_out_while_mafia / self.games_as_mafia if self.games_as_mafia else 0.0

    @property
    def friendly_fire_rate(self) -> float:
        """How often this model got wrongly voted out while playing town."""
        return self.voted_out_while_town / self.games_as_town if self.games_as_town else 0.0

    @property
    def avg_cost_per_game(self) -> float:
        return self.total_cost_usd / self.games if self.games else 0.0

    @property
    def cost_per_win(self) -> float | None:
        return self.total_cost_usd / self.wins if self.wins else None


ELO_K = 24.0
ELO_BASE = 1500.0


def _team_expected(own_avg: float, opp_avg: float) -> float:
    return 1.0 / (1.0 + 10 ** ((opp_avg - own_avg) / 400.0))


def compute_leaderboard(summary_path: str) -> dict[str, ModelStats]:
    stats: dict[str, ModelStats] = {}

    def get(key: str) -> ModelStats:
        if key not in stats:
            stats[key] = ModelStats(model_key=key)
        return stats[key]

    with open(summary_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            game = json.loads(line)
            winner = game.get("winner")
            days = max(game.get("days", 1), 1)
            players = game["players"]

            for p in players:
                s = get(p["model_key"])
                s.games += 1
                survived_days = p["death_day"] if p["death_day"] is not None else days
                s.survival_day_fraction_sum += min(survived_days / days, 1.0)

                if p["team"] == "mafia":
                    s.games_as_mafia += 1
                    if winner == "mafia":
                        s.wins_as_mafia += 1
                        s.wins += 1
                    if p["death_cause"] == "voted_out":
                        s.voted_out_while_mafia += 1
                else:
                    s.games_as_town += 1
                    if winner == "town":
                        s.wins_as_town += 1
                        s.wins += 1
                    if p["death_cause"] == "voted_out":
                        s.voted_out_while_town += 1

            for key, count in game.get("format_failures", {}).items():
                get(key).format_failures += count

            for key, amount in game.get("cost_usd", {}).items():
                get(key).total_cost_usd += amount

            if winner in ("mafia", "town"):
                mafia_players = [p for p in players if p["team"] == "mafia"]
                town_players = [p for p in players if p["team"] == "town"]
                mafia_avg = sum(get(p["model_key"]).elo for p in mafia_players) / len(mafia_players)
                town_avg = sum(get(p["model_key"]).elo for p in town_players) / len(town_players)

                mafia_expected = _team_expected(mafia_avg, town_avg)
                town_expected = _team_expected(town_avg, mafia_avg)
                mafia_actual = 1.0 if winner == "mafia" else 0.0
                town_actual = 1.0 if winner == "town" else 0.0

                mafia_delta = ELO_K * (mafia_actual - mafia_expected)
                town_delta = ELO_K * (town_actual - town_expected)

                for p in mafia_players:
                    get(p["model_key"]).elo += mafia_delta
                for p in town_players:
                    get(p["model_key"]).elo += town_delta

    return stats


def render_markdown_table(stats: dict[str, ModelStats]) -> str:
    rows = sorted(stats.values(), key=lambda s: s.elo, reverse=True)
    header = (
        "| Rank | Model | Elo | Games | Win Rate | Mafia WR | Town WR | "
        "Caught as Mafia | Friendly-Fired | Format Fails | Total Cost | $/Game | $/Win |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
    )
    lines = [header]
    for i, s in enumerate(rows, start=1):
        cost_per_win = f"${s.cost_per_win:.4f}" if s.cost_per_win is not None else "-"
        lines.append(
            f"| {i} | {s.model_key} | {s.elo:.0f} | {s.games} | {s.win_rate:.0%} | "
            f"{s.mafia_win_rate:.0%} | {s.town_win_rate:.0%} | {s.detection_rate_against:.0%} | "
            f"{s.friendly_fire_rate:.0%} | {s.format_failures} | ${s.total_cost_usd:.4f} | "
            f"${s.avg_cost_per_game:.4f} | {cost_per_win} |\n"
        )
    total_cost = sum(s.total_cost_usd for s in rows)
    lines.append(f"\nTotal spend across all games: ${total_cost:.4f}\n")
    return "".join(lines)
