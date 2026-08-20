from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass

from ..agents.player_agent import PlayerAgent
from ..providers.base import ChatProvider
from . import prompts
from .roles import Role
from .state import GameState
from .summarizer import summarize_day


@dataclass
class GameResult:
    state: GameState
    winner: str | None  # "mafia" | "town" | None (draw/timeout)
    days: int


MAX_MESSAGES_PER_TURN = 3


def _extract_messages(reply: dict) -> list[str]:
    """Pulls up to MAX_MESSAGES_PER_TURN non-empty strings out of a reply's
    "messages" list, falling back to the legacy single "message" key (used by
    PlayerAgent's format-failure fallback) if "messages" wasn't provided.
    """
    raw = reply.get("messages")
    if not isinstance(raw, list) or not raw:
        raw = [reply.get("message", "(no response)")]
    return [str(m) for m in raw if str(m).strip()][:MAX_MESSAGES_PER_TURN] or ["(no response)"]


class GameEngine:
    def __init__(
        self,
        state: GameState,
        agents: dict[str, PlayerAgent],
        rules: dict,
        summarizer: ChatProvider | None = None,
        summarizer_key: str | None = None,
    ):
        self.state = state
        self.agents = agents  # seat -> PlayerAgent
        self.rules = rules
        # Optional dedicated model (never one of the roster models under
        # evaluation) that compresses each day's discussion into one sentence
        # once it ages out of the full-detail window, instead of losing it
        # outright. Opt-in via rules["summarizer_model"] -- see tournament.py.
        self.summarizer = summarizer
        self.summarizer_key = summarizer_key

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
            self._maybe_summarize_day(state.day)
            winner = state.winner()
            if winner:
                return GameResult(state, winner, state.day)

        return GameResult(state, None, state.day)

    def _maybe_summarize_day(self, day: int) -> None:
        if not self.summarizer:
            return
        speech = [e for e in self.state.public_log if e.day == day and e.kind == "speech"]
        if not speech:
            return
        text = "\n".join(f"{e.speaker}: {e.text}" for e in speech)
        summary, resp = summarize_day(self.summarizer, day, text, self.rules)
        self.state.add_cost(self.summarizer_key or "summarizer", resp.cost_usd)
        if summary:
            self.state.day_summaries[day] = summary

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
                required_keys=["messages", "target"],
                target_keys={"target": candidates},
            )
            state.log_thought("night", p.seat, str(reply.get("thought", "")))
            for msg in _extract_messages(reply):
                state.log_mafia("mafia_chat", msg, speaker=p.seat)
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
            state.log_thought("night", p.seat, str(reply.get("thought", "")))
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
            state.log_thought("night", p.seat, str(reply.get("thought", "")))
            target_seat = reply.get("investigate")
            if target_seat:
                role = state.get(target_seat).role.value
                p.private_notes.append(f"Night {state.day}: investigated {target_seat} -> role is {role}")

        if kill_target and kill_target != doctor_save and state.get(kill_target).alive:
            state.kill(kill_target, "killed")
            if self.rules.get("reveal_role_on_death"):
                role = state.get(kill_target).role.value
                state.log_public("day", "system", f"{kill_target} died. They were {role}.")
            else:
                state.log_public("day", "system", f"{kill_target} died.")
        else:
            state.log_public("day", "system", "No one died.")

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
                    required_keys=["messages"],
                )
                state.log_thought("day", p.seat, str(reply.get("thought", "")))
                for msg in _extract_messages(reply):
                    state.log_public("day", "speech", msg, speaker=p.seat)

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
            state.log_thought("day", p.seat, str(reply.get("thought", "")))
            target = reply.get("vote")
            if target:
                votes[p.seat] = target
                state.log_public("day", "vote", f"{p.seat} votes for {target}", speaker=p.seat)

        state.day_votes.append({"day": state.day, "votes": votes})

        voted_out = _resolve_vote(votes, self.rules.get("tie_vote_policy", "random"))
        if voted_out:
            state.kill(voted_out, "voted_out")
            if self.rules.get("reveal_role_on_death"):
                role = state.get(voted_out).role.value
                state.log_public("day", "system", f"{voted_out} died. They were {role}.")
            else:
                state.log_public("day", "system", f"{voted_out} died.")
        else:
            state.log_public("day", "system", "The vote was tied; no one died.")


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
    if tie_policy == "no_elimination":
        return None
    return random.choice(winners)
