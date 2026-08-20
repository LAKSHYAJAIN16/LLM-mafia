from __future__ import annotations

import random
import re
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


MAX_MESSAGES_PER_TURN = 4  # burst cap for night mafia chat
DEFAULT_MAX_MESSAGES_PER_DAY = 5  # per-player daily budget for the open-floor day discussion, unless rules overrides it


def _extract_messages(reply: dict) -> list[str]:
    """Pulls up to MAX_MESSAGES_PER_TURN non-empty strings out of a reply's
    "messages" list, falling back to the legacy single "message" key (used by
    PlayerAgent's format-failure fallback) if "messages" wasn't provided. Used for
    night mafia chat only -- showdown defense is one longer speech, not a burst.
    """
    raw = reply.get("messages")
    if not isinstance(raw, list) or not raw:
        raw = [reply.get("message", "(no response)")]
    return [str(m) for m in raw if str(m).strip()][:MAX_MESSAGES_PER_TURN] or ["(no response)"]


_SEAT_MENTION_RE = re.compile(r"\bPlayer\d+\b")


def _mentioned_seats(text: str, valid_seats, exclude_seat: str) -> list[str]:
    """Distinct player seats named in a message, in first-mention order, excluding
    the speaker's own seat and anything that isn't a real current seat -- used to
    let a directly-addressed player jump the discussion queue (see _run_discussion),
    the same way a real conversation gives the floor to whoever was just asked
    something, instead of a flat fair rotation ignoring who's talking to whom.
    """
    seen: list[str] = []
    for m in _SEAT_MENTION_RE.findall(text):
        if m != exclude_seat and m in valid_seats and m not in seen:
            seen.append(m)
    return seen


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
            if self._budget_exceeded():
                state.log_public("day", "system", self._budget_message())
                return GameResult(state, None, state.day)

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

    def _total_cost(self) -> float:
        return sum(self.state.cost_usd.values())

    def _budget_exceeded(self) -> bool:
        return self._budget_exceeded_reason() is not None

    def _budget_exceeded_reason(self) -> str | None:
        total = self._total_cost()

        cap = self.rules.get("max_cost_usd")
        if cap and total >= cap:
            return f"cost cap (${cap:.2f}) reached (spent ${total:.4f})"

        return None

    def _budget_message(self) -> str:
        return f"Game stopped early: {self._budget_exceeded_reason()}."

    def _maybe_summarize_day(self, day: int) -> None:
        if not self.summarizer:
            return
        # Lazy, not eager: only summarize the one day that is about to fall out of
        # the full-detail window as of *next* day's cutoff, so a game that never
        # runs long enough to need a summary never pays for one.
        target_day = day - self.state.transcript_full_detail_days
        if target_day < 1 or target_day in self.state.day_summaries:
            return
        speech = [e for e in self.state.public_log if e.day == target_day and e.kind == "speech"]
        if not speech:
            return
        text = "\n".join(f"{e.speaker}: {e.text}" for e in speech)
        summary, resp, sys_prompt, user_prompt = summarize_day(self.summarizer, target_day, text, self.rules)
        self.state.log_raw_call(
            seat=None,
            model_key=self.summarizer_key,
            purpose="day_summary",
            attempt=1,
            system_prompt=sys_prompt,
            user_prompt=user_prompt,
            response_text=resp.text,
            error=resp.error,
            cost_usd=resp.cost_usd,
        )
        self.state.add_cost(self.summarizer_key or "summarizer", resp.cost_usd)
        if summary:
            self.state.day_summaries[target_day] = summary

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
                seat=p.seat,
                purpose="night_mafia",
            )
            state.log_thought("night", p.seat, str(reply.get("thought", "")))
            for msg in _extract_messages(reply):
                state.log_mafia("mafia_chat", msg, speaker=p.seat)
            if "target" in reply:
                proposals.append(reply["target"])

        kill_target = _majority_choice(proposals)

        doctor_save: str | None = None
        attack_blocked = False
        for p in state.alive_by_role(Role.DOCTOR):
            candidates = [s.seat for s in state.alive_players()]
            reply = self.agents[p.seat].ask(
                state,
                prompts.build_system_prompt(state, p),
                prompts.build_night_doctor_prompt(state, p),
                required_keys=["save"],
                target_keys={"save": candidates},
                seat=p.seat,
                purpose="night_doctor",
            )
            state.log_thought("night", p.seat, str(reply.get("thought", "")))
            doctor_save = reply.get("save")

            # Reveal (and note) the outcome right here, immediately after the doctor's
            # own action -- not batched in afterward, so the replay/console shows each
            # player's outcome right after that player acted, in true turn order.
            attack_blocked = bool(kill_target and doctor_save and kill_target == doctor_save)
            if doctor_save:
                if attack_blocked:
                    p.private_notes.append(
                        f"Night {state.day}: you protected {doctor_save} -- {doctor_save} was attacked and you saved them!"
                    )
                    state.log_reveal("night", p.seat, f"{p.seat} protected {doctor_save} -- {doctor_save} was saved!")
                else:
                    p.private_notes.append(
                        f"Night {state.day}: you protected {doctor_save}. No attack landed on them that night."
                    )
                    state.log_reveal("night", p.seat, f"{p.seat} protected {doctor_save}. No attack landed on them.")

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
                seat=p.seat,
                purpose="night_detective",
            )
            state.log_thought("night", p.seat, str(reply.get("thought", "")))
            target_seat = reply.get("investigate")
            if target_seat:
                role = state.get(target_seat).role.value
                p.private_notes.append(
                    f"Night {state.day}: you investigated {target_seat} -- they are {role}. You now know this."
                )
                # Spectator-only reveal (console/HTML replay) -- never reaches another
                # player's prompt, only this detective's own private_notes above do.
                state.log_reveal("night", p.seat, f"{p.seat} investigated {target_seat} -- {target_seat} is {role}.")

        if kill_target and not attack_blocked and state.get(kill_target).alive:
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
        self._run_discussion()
        voted_out = self._run_vote_with_showdowns()
        if voted_out:
            state.kill(voted_out, "voted_out")
            if self.rules.get("reveal_role_on_death"):
                role = state.get(voted_out).role.value
                state.log_public("day", "system", f"{voted_out} died. They were {role}.")
            else:
                state.log_public("day", "system", f"{voted_out} died.")
        else:
            state.log_public("day", "system", "The vote was tied; no one died.")

    def _run_discussion(self) -> None:
        """Runs day discussion as an open floor rather than a fixed speaking order:
        one random player is picked to open, then each subsequent turn taps one alive
        player to decide whether to speak (exactly one message), think privately, or
        pass. Whoever was just addressed by name jumps the queue -- a real
        conversation gives the floor to whoever was just asked something, not a flat
        fair rotation that ignores who's talking to whom -- otherwise turns cycle
        fairly through everyone still eligible. A real conversation doesn't poll every
        participant before concluding the room's gone quiet, so discussion ends as
        soon as discussion_silence_threshold consecutive taps in a row produce no
        speaker -- not only once literally everyone has individually declined -- with
        one floor: nobody alive can be shut out of a whole day without a single turn.
        If the room goes quiet while someone still hasn't been polled even once today
        (observed in a real 15-player game: two players locked in a back-and-forth
        kept getting priority all day, and a third player never got asked once), they
        get the floor before the day is allowed to end. This is also the main cost
        lever: the expensive case was always the tail end of a day, burning one call
        per remaining player just to confirm nobody had anything left to add.
        max_discussion_polls_per_day is a hard safety backstop, not expected to bind
        in normal play.
        """
        state = self.state
        alive = state.alive_players()
        if not alive:
            return
        max_per_day = self.rules.get("max_messages_per_day", DEFAULT_MAX_MESSAGES_PER_DAY)
        budget = {p.seat: max_per_day for p in alive}

        opener = random.choice(alive)
        opener_msg = self._speak_opening(opener, budget)
        priority: list[str] = []
        addressed_by: dict[str, tuple[str, str]] = {}
        self._note_mentions(opener_msg, opener.seat, budget.keys(), priority, addressed_by)

        max_polls = self.rules.get("max_discussion_polls_per_day", 1000)
        quiet_limit = self.rules.get("discussion_silence_threshold", 6)
        polls_used = 0
        consecutive_quiet = 0
        queue: list = []
        polled_today: set[str] = {opener.seat}

        while polls_used < max_polls:
            if self._budget_exceeded():
                break
            candidates = [p for p in state.alive_players() if budget[p.seat] > 0]
            if not candidates:
                break

            by_seat = {c.seat: c for c in candidates}
            never_polled = [c for c in candidates if c.seat not in polled_today]
            next_player = None

            if consecutive_quiet >= quiet_limit and never_polled:
                # The room's gone quiet by the normal rule, but someone alive still
                # hasn't had a single turn today -- give them the floor before the day
                # is allowed to end, so two players dominating a back-and-forth can't
                # shut a third voice out entirely.
                next_player = never_polled[0]
                queue = [q for q in queue if q.seat != next_player.seat]
                priority = [s for s in priority if s != next_player.seat]
            else:
                while priority:
                    seat = priority.pop(0)
                    if seat in by_seat:
                        next_player = by_seat[seat]
                        break
                    addressed_by.pop(seat, None)  # no longer eligible -- drop the stale nudge
                if next_player is not None:
                    queue = [q for q in queue if q.seat != next_player.seat]
                else:
                    # Refill the turn-taking queue (a fair, reshuffled cycle through
                    # everyone still eligible) whenever it's empty or references someone
                    # who's since used up their daily budget.
                    queue = [q for q in queue if budget[q.seat] > 0]
                    if not queue:
                        queue = candidates[:]
                        random.shuffle(queue)
                    next_player = queue.pop(0)

            polls_used += 1
            polled_today.add(next_player.seat)
            nudge = addressed_by.pop(next_player.seat, None)
            msg = self._poll_speak(next_player, budget, max_per_day, addressed_by=nudge)
            if msg is not None:
                consecutive_quiet = 0
                self._note_mentions(msg, next_player.seat, budget.keys(), priority, addressed_by)
            else:
                consecutive_quiet += 1
                still_never_polled = any(c.seat not in polled_today for c in state.alive_players() if budget[c.seat] > 0)
                if consecutive_quiet >= quiet_limit and not still_never_polled:
                    break

    @staticmethod
    def _note_mentions(
        text: str,
        speaker_seat: str,
        valid_seats,
        priority: list[str],
        addressed_by: dict[str, tuple[str, str]],
    ) -> None:
        """Records who a message named, so they jump the discussion queue next and
        get told directly they were addressed (see _poll_speak) -- the difference
        between a fair rotation and a conversation that actually responds to itself.
        """
        for seat in _mentioned_seats(text, valid_seats, speaker_seat):
            if seat not in priority:
                priority.append(seat)
            addressed_by[seat] = (speaker_seat, text)

    @staticmethod
    def _speaking_rate_nudge(state: GameState, seat: str, participant_seats) -> str | None:
        """Mirrors the dynamic scheduler-prompt bias from Eckhaus et al. 2025 ("Time
        to Talk: LLM Agents for Asynchronous Group Communication in Mafia Games"):
        nudge a player who's spoken less than their fair share (1/n) of today's
        messages to speak up, and one who's spoken more than their fair share to
        listen more. Opt-in via rules["dynamic_speaking_rate_nudge"] -- off by
        default, so the game plays exactly as it does today unless explicitly
        turned on.
        """
        today = [e for e in state.public_log if e.day == state.day and e.kind == "speech"]
        total = len(today)
        n = len(list(participant_seats))
        if total == 0 or n == 0:
            return None
        fair_share = 1 / n
        mine = sum(1 for e in today if e.speaker == seat)
        rate = mine / total
        if rate < fair_share * 0.5:
            return "quiet"
        if rate > fair_share * 1.5:
            return "talkative"
        return None

    def _speak_opening(self, p, budget: dict[str, int]) -> str:
        state = self.state
        reply = self.agents[p.seat].ask(
            state,
            prompts.build_system_prompt(state, p),
            prompts.build_day_discussion_open_prompt(state),
            required_keys=["message"],
            seat=p.seat,
            purpose="day_discussion_open",
        )
        state.log_thought("day", p.seat, str(reply.get("thought", "")))
        msg = str(reply.get("message", "")).strip() or "(no response)"
        state.log_public("day", "speech", msg, speaker=p.seat)
        budget[p.seat] -= 1
        return msg

    def _poll_speak(
        self, p, budget: dict[str, int], max_per_day: int, addressed_by: tuple[str, str] | None = None
    ) -> str | None:
        """Asks one player whether they want to speak right now. Returns their
        message (and posts it) if they chose to speak, None if they chose to think
        or stay silent -- in which case nothing public happens this turn.
        addressed_by, if set, is (seat, message) of whoever just named this player --
        surfaced explicitly in the prompt so it actually reads as being put on the
        spot, not just something they might notice buried in the transcript.
        """
        state = self.state
        rate_nudge = None
        if self.rules.get("dynamic_speaking_rate_nudge"):
            rate_nudge = self._speaking_rate_nudge(state, p.seat, budget.keys())
        reply = self.agents[p.seat].ask(
            state,
            prompts.build_system_prompt(state, p),
            prompts.build_day_discussion_poll_prompt(
                state, budget[p.seat], max_per_day, addressed_by=addressed_by, rate_nudge=rate_nudge
            ),
            required_keys=["action"],
            seat=p.seat,
            purpose="day_discussion_poll",
        )
        thought = str(reply.get("thought", ""))
        if thought:
            state.log_thought("day", p.seat, thought)

        action = str(reply.get("action", "pass")).strip().lower()
        if action != "speak":
            return None

        msg = str(reply.get("message", "")).strip()
        if not msg:
            return None  # chose to speak but produced nothing -- treat as a pass, don't burn budget

        state.log_public("day", "speech", msg, speaker=p.seat)
        budget[p.seat] -= 1
        return msg

    def _run_vote_with_showdowns(self) -> str | None:
        """Runs the day's ballot. Votes are secret -- see state.log_vote -- so no
        player ever learns who voted for whom, only the eventual outcome. A tie at
        the top goes to a showdown: the tied players get to publicly make their case,
        then everyone revotes among just the tied set. Repeats (bounded by
        max_showdown_rounds) until one player has sole possession of the most votes.
        """
        state = self.state
        max_rounds = self.rules.get("max_showdown_rounds", 5)
        candidates = [p.seat for p in state.alive_players()]

        round_num = 0
        while True:
            round_num += 1
            votes = self._collect_votes(candidates, round_num)
            state.day_votes.append({"day": state.day, "round": round_num, "votes": votes})

            if not votes:
                return None
            counts = Counter(votes.values())
            top = counts.most_common()
            best_count = top[0][1]
            tied = [name for name, c in top if c == best_count]
            if len(tied) == 1:
                return tied[0]

            if round_num >= max_rounds or self._budget_exceeded():
                if self.rules.get("tie_vote_policy", "random") == "no_elimination":
                    return None
                return random.choice(tied)

            state.log_public(
                "day",
                "system",
                f"The vote is tied between {', '.join(tied)}. Showdown: each gets to make their case before a revote.",
            )
            self._run_showdown_defense(tied)
            candidates = tied

    def _collect_votes(self, candidates: list[str], round_num: int) -> dict[str, str]:
        state = self.state
        order = state.alive_players()
        random.shuffle(order)
        votes: dict[str, str] = {}
        for p in order:
            # Nobody can vote for themselves -- you always have to accuse someone
            # else. (Previously self-votes were technically allowed "if you have no
            # better option," which in practice models took as an easy out under
            # pressure instead of committing to a real accusation.)
            voter_candidates = [c for c in candidates if c != p.seat] or candidates
            if round_num == 1:
                prompt = prompts.build_day_vote_prompt(state, p)
            else:
                prompt = prompts.build_day_showdown_vote_prompt(state, p, candidates)
            reply = self.agents[p.seat].ask(
                state,
                prompts.build_system_prompt(state, p),
                prompt,
                required_keys=["vote"],
                target_keys={"vote": voter_candidates},
                seat=p.seat,
                purpose="day_vote" if round_num == 1 else "day_showdown_vote",
            )
            state.log_thought("day", p.seat, str(reply.get("thought", "")))
            target = reply.get("vote")
            if target:
                votes[p.seat] = target
                # Secret ballot: recorded for spectators/replay only, never fed back
                # into public_transcript_text() -- see state.log_vote.
                state.log_vote("day", p.seat, f"{p.seat} votes for {target}")
        return votes

    def _run_showdown_defense(self, accused: list[str]) -> None:
        """Only the tied players get to speak in a showdown, not the whole table --
        each gets exactly one turn, but as a real speech (one longer paragraph, with
        extra token headroom via showdown_max_tokens) rather than the usual short
        chat-style burst.
        """
        state = self.state
        order = [p for p in state.alive_players() if p.seat in accused]
        random.shuffle(order)
        max_tokens = self.rules.get("showdown_max_tokens") or self.rules.get("max_tokens", 500)
        for p in order:
            reply = self.agents[p.seat].ask(
                state,
                prompts.build_system_prompt(state, p),
                prompts.build_day_showdown_defense_prompt(state, p, accused),
                required_keys=["speech"],
                seat=p.seat,
                purpose="day_showdown_defense",
                max_tokens=max_tokens,
            )
            state.log_thought("day", p.seat, str(reply.get("thought", "")))
            speech = str(reply.get("speech", "")).strip() or "(no response)"
            state.log_public("day", "speech", speech, speaker=p.seat)


def _majority_choice(proposals: list[str]) -> str | None:
    if not proposals:
        return None
    counts = Counter(proposals)
    top = counts.most_common()
    best_count = top[0][1]
    winners = [name for name, c in top if c == best_count]
    return random.choice(winners)
