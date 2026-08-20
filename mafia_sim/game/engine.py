from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass

from ..agents.player_agent import PlayerAgent
from . import prompts
from .roles import Role
from .state import GameState


@dataclass
class GameResult:
    state: GameState
    winner: str | None  # "mafia" | "town" | None (draw/timeout)
    days: int


class GameEngine:
    def __init__(self, state: GameState, agents: dict[str, PlayerAgent], rules: dict):
        self.state = state
        self.agents = agents  # seat -> PlayerAgent
        self.rules = rules

    def run(self) -> GameResult:
        state = self.state
        state.log_public("day", "system", "The game begins. Roles have been secretly assigned.")

        max_days = self.rules.get("max_days", 20)
        while state.day < max_days:
            state.day += 1

            self._run_night()
            winner = state.winner()
            if winner:
                return GameResult(state, winner, state.day)

            self._run_day()
            winner = state.winner()
            if winner:
                return GameResult(state, winner, state.day)

        return GameResult(state, None, state.day)

    # -- night phase -----------------------------------------------------

    def _run_night(self) -> None:
        state = self.state
        mafia = state.alive_by_role(Role.MAFIA)
        mafia_seats = [p.seat for p in mafia]

        proposals: list[str] = []
        for p in mafia:
            candidates = [s.seat for s in state.alive_players() if s.seat not in mafia_seats]
            if not candidates:
                break
            reply = self.agents[p.seat].ask(
                state,
                prompts.build_system_prompt(state, p),
                prompts.build_night_mafia_prompt(state, p),
                required_keys=["message", "target"],
                target_keys={"target": candidates},
            )
            state.log_mafia("mafia_chat", reply.get("message", ""), speaker=p.seat)
            if "target" in reply:
                proposals.append(reply["target"])

        kill_target = _majority_choice(proposals)

        doctor_save: str | None = None
        for p in state.alive_by_role(Role.DOCTOR):
            candidates = [s.seat for s in state.alive_players()]
            reply = self.agents[p.seat].ask(
                state,
                prompts.build_system_prompt(state, p),
                prompts.build_night_doctor_prompt(state, p),
                required_keys=["save"],
                target_keys={"save": candidates},
            )
            doctor_save = reply.get("save")

        for p in state.alive_by_role(Role.DETECTIVE):
            candidates = [s.seat for s in state.alive_players() if s.seat != p.seat]
            if not candidates:
                continue
            reply = self.agents[p.seat].ask(
                state,
                prompts.build_system_prompt(state, p),
                prompts.build_night_detective_prompt(state, p),
                required_keys=["investigate"],
                target_keys={"investigate": candidates},
            )
            target_seat = reply.get("investigate")
            if target_seat:
                team = state.get(target_seat).role.team
                p.private_notes.append(f"Night {state.day}: investigated {target_seat} -> {team}")

        if kill_target and kill_target != doctor_save and state.get(kill_target).alive:
            state.kill(kill_target, "killed")
            if self.rules.get("reveal_role_on_death"):
                role = state.get(kill_target).role.value
                state.log_public("day", "system", f"{kill_target} was found dead. They were {role}.")
            else:
                state.log_public("day", "system", f"{kill_target} was found dead during the night.")
        else:
            state.log_public("day", "system", "No one died during the night.")

    # -- day phase ---------------------------------------------------------

    def _run_day(self) -> None:
        state = self.state
        rounds = self.rules.get("discussion_rounds_per_day", 1)

        for _ in range(rounds):
            order = state.alive_players()
            random.shuffle(order)
            for p in order:
                reply = self.agents[p.seat].ask(
                    state,
                    prompts.build_system_prompt(state, p),
                    prompts.build_day_discussion_prompt(state),
                    required_keys=["message"],
                )
                state.log_public("day", "speech", reply.get("message", ""), speaker=p.seat)

        order = state.alive_players()
        random.shuffle(order)
        votes: dict[str, str] = {}
        for p in order:
            candidates = [s.seat for s in state.alive_players()]
            reply = self.agents[p.seat].ask(
                state,
                prompts.build_system_prompt(state, p),
                prompts.build_day_vote_prompt(state),
                required_keys=["vote"],
                target_keys={"vote": candidates},
            )
            target = reply.get("vote")
            if target:
                votes[p.seat] = target
                state.log_public("day", "vote", f"{p.seat} votes for {target}", speaker=p.seat)

        state.day_votes.append({"day": state.day, "votes": votes})

        lynched = _resolve_vote(votes, self.rules.get("tie_vote_policy", "random"))
        if lynched:
            state.kill(lynched, "lynched")
            if self.rules.get("reveal_role_on_death"):
                role = state.get(lynched).role.value
                state.log_public("day", "system", f"{lynched} was lynched by the town. They were {role}.")
            else:
                state.log_public("day", "system", f"{lynched} was lynched by the town.")
        else:
            state.log_public("day", "system", "The vote was tied; no one was lynched.")


def _majority_choice(proposals: list[str]) -> str | None:
    if not proposals:
        return None
    counts = Counter(proposals)
    top = counts.most_common()
    best_count = top[0][1]
    winners = [name for name, c in top if c == best_count]
    return random.choice(winners)


def _resolve_vote(votes: dict[str, str], tie_policy: str) -> str | None:
    if not votes:
        return None
    counts = Counter(votes.values())
    top = counts.most_common()
    best_count = top[0][1]
    winners = [name for name, c in top if c == best_count]
    if len(winners) == 1:
        return winners[0]
    if tie_policy == "no_lynch":
        return None
    return random.choice(winners)
