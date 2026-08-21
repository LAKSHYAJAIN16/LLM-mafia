from __future__ import annotations

from collections import defaultdict

# MafiaSim's roster spans many distinct model vendors in the same game (unlike most
# published Werewolf/Mafia LLM-agent work, which runs one model family against itself
# or against humans). That's a real, otherwise-unmeasured question: does one model
# family have a systematic blind spot against a specific *other* family's deception
# style, not just a lower aggregate skill? This module answers it from data we already
# log -- day_votes (secret ballots, spectator-only) plus each player's role and model --
# no new gameplay mechanic or extra API calls required.


def _alive_at_day(player: dict, day: int) -> bool:
    death_day = player.get("death_day")
    return death_day is None or death_day >= day


def compute_deception_matrix(games: list[dict]) -> dict[tuple[str, str], dict[str, int]]:
    """For every (accuser_model, mafia_model) pair, counts:
    - "opportunities": how many times a non-mafia voter had a specific alive mafia
      player available as a legal vote target that day.
    - "catches": how many of those opportunities the voter actually spent voting for
      that mafia player (a successful read), rather than someone else (the mafia
      player successfully evaded suspicion from that specific accuser that round).

    Keyed by (accuser_model_key, mafia_model_key). catches/opportunities is the
    accuser's detection rate against that mafia model; 1 minus it is the mafia
    model's deception success rate against that specific accuser.
    """
    counts: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: {"opportunities": 0, "catches": 0})

    for game in games:
        players_by_seat = {p["seat"]: p for p in game.get("players", [])}
        for round_entry in game.get("day_votes", []):
            day = round_entry["day"]
            votes = round_entry.get("votes", {})
            alive_mafia_seats = [
                seat for seat, p in players_by_seat.items() if p.get("role") == "mafia" and _alive_at_day(p, day)
            ]
            if not alive_mafia_seats:
                continue
            for voter_seat, target_seat in votes.items():
                voter = players_by_seat.get(voter_seat)
                if voter is None or voter.get("role") == "mafia":
                    continue  # only non-mafia accusers -- mafia voting mafia isn't "deception"
                voter_model = voter["model_key"]
                for mafia_seat in alive_mafia_seats:
                    if mafia_seat == voter_seat:
                        continue
                    mafia_model = players_by_seat[mafia_seat]["model_key"]
                    key = (voter_model, mafia_model)
                    counts[key]["opportunities"] += 1
                    if target_seat == mafia_seat:
                        counts[key]["catches"] += 1

    return dict(counts)


def render_markdown_table(matrix: dict[tuple[str, str], dict[str, int]], min_opportunities: int = 1) -> str:
    rows = []
    for (accuser, deceiver), c in matrix.items():
        opportunities = c["opportunities"]
        if opportunities < min_opportunities:
            continue
        catches = c["catches"]
        rate = catches / opportunities if opportunities else 0.0
        rows.append((accuser, deceiver, opportunities, catches, rate))

    if not rows:
        return f"No accuser/mafia pairs with at least {min_opportunities} opportunity(ies) yet -- run more games."

    rows.sort(key=lambda r: (-r[2], -r[4]))
    lines = [
        "| Accuser (town-side voter) | Deceiver (mafia) | Opportunities | Caught | Catch Rate |",
        "|---|---|---|---|---|",
    ]
    for accuser, deceiver, opportunities, catches, rate in rows:
        lines.append(f"| {accuser} | {deceiver} | {opportunities} | {catches} | {rate:.0%} |")
    lines.append("")
    lines.append(
        "Catch Rate is the accuser's detection rate against that specific deceiver model; "
        "1 - Catch Rate is that deceiver's deception success rate against that specific accuser. "
        "Small opportunity counts are noisy -- treat rows under ~10 opportunities as directional, not conclusive."
    )
    return "\n".join(lines)
