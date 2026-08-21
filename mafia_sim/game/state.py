from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .roles import Role


@dataclass
class Player:
    seat: str  # e.g. "Player3" -- the only identity other players ever see
    model_key: str  # which roster entry is behind this seat (hidden from other players)
    role: Role
    alive: bool = True
    death_day: int | None = None
    death_cause: str | None = None  # "voted_out" | "killed" | None
    private_notes: list[str] = field(default_factory=list)
    investigated: dict[str, str] = field(default_factory=dict)  # detective only: seat -> role already learned


@dataclass
class LogEntry:
    day: int
    phase: str  # "night" | "day"
    kind: str  # "system" | "speech" | "vote" | "mafia_chat" | "thought"
    speaker: str | None
    text: str
    seq: int = 0  # global monotonic order across public/mafia/thought logs, for replay ordering


@dataclass
class GameState:
    players: list[Player]
    public_log: list[LogEntry] = field(default_factory=list)
    mafia_log: list[LogEntry] = field(default_factory=list)
    thought_log: list[LogEntry] = field(default_factory=list)  # spectator-only private reasoning
    vote_log: list[LogEntry] = field(default_factory=list)  # spectator-only -- ballots are secret from players
    reveal_log: list[LogEntry] = field(default_factory=list)  # spectator-only -- doctor save / detective investigation outcomes
    day: int = 0
    _seq: int = field(default=0, repr=False, compare=False)
    day_votes: list[dict] = field(default_factory=list)  # [{day, round, votes: {voter: target}}]
    format_failures: dict[str, int] = field(default_factory=dict)  # model_key -> count
    cost_usd: dict[str, float] = field(default_factory=dict)  # model_key -> accumulated $ spend
    transcript_full_detail_days: int = 3  # older "speech" entries are dropped to bound prompt growth
    day_summaries: dict[int, str] = field(default_factory=dict)  # day -> 1-sentence summary (opt-in)
    raw_calls: list[dict] = field(default_factory=list)  # exact (system_prompt, user_prompt) -> raw response text, every LLM call
    on_event: Callable[[LogEntry], None] | None = field(default=None, repr=False, compare=False)

    def get(self, seat: str) -> Player:
        for p in self.players:
            if p.seat == seat:
                return p
        raise KeyError(seat)

    def alive_players(self) -> list[Player]:
        return [p for p in self.players if p.alive]

    def alive_by_role(self, role: Role) -> list[Player]:
        return [p for p in self.alive_players() if p.role == role]

    def mafia_alive(self) -> list[Player]:
        return [p for p in self.alive_players() if p.role.team == "mafia"]

    def town_alive(self) -> list[Player]:
        return [p for p in self.alive_players() if p.role.team == "town"]

    def winner(self) -> str | None:
        mafia = len(self.mafia_alive())
        town = len(self.town_alive())
        if mafia == 0:
            return "town"
        if mafia >= town:
            return "mafia"
        return None

    def kill(self, seat: str, cause: str) -> None:
        p = self.get(seat)
        p.alive = False
        p.death_day = self.day
        p.death_cause = cause

    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq

    def log_public(self, phase: str, kind: str, text: str, speaker: str | None = None) -> None:
        entry = LogEntry(self.day, phase, kind, speaker, text, seq=self._next_seq())
        self.public_log.append(entry)
        if self.on_event:
            self.on_event(entry)

    def log_mafia(self, kind: str, text: str, speaker: str | None = None) -> None:
        entry = LogEntry(self.day, "night", kind, speaker, text, seq=self._next_seq())
        self.mafia_log.append(entry)
        if self.on_event:
            self.on_event(entry)

    def log_thought(self, phase: str, speaker: str, text: str) -> None:
        if not text.strip():
            return
        entry = LogEntry(self.day, phase, "thought", speaker, text, seq=self._next_seq())
        self.thought_log.append(entry)
        if self.on_event:
            self.on_event(entry)

    def log_vote(self, phase: str, speaker: str, text: str) -> None:
        # Ballots are secret: this goes to vote_log (spectator-only, e.g. the HTML
        # replay), never to public_log, so public_transcript_text() -- the only thing
        # that feeds a player's prompt -- never reveals who voted for whom.
        entry = LogEntry(self.day, phase, "vote", speaker, text, seq=self._next_seq())
        self.vote_log.append(entry)
        if self.on_event:
            self.on_event(entry)

    def log_reveal(self, phase: str, speaker: str, text: str) -> None:
        # Spectator-only, like votes/thoughts: lets a human watching (console live
        # feed or replay) see what the doctor's save actually did and what the
        # detective actually learned, without that ever reaching another player's
        # prompt -- the private_notes copy (see engine.py) is what the player
        # themselves gets to act on.
        entry = LogEntry(self.day, phase, "reveal", speaker, text, seq=self._next_seq())
        self.reveal_log.append(entry)
        if self.on_event:
            self.on_event(entry)

    def note_format_failure(self, model_key: str) -> None:
        self.format_failures[model_key] = self.format_failures.get(model_key, 0) + 1

    def add_cost(self, model_key: str, amount: float) -> None:
        if amount:
            self.cost_usd[model_key] = self.cost_usd.get(model_key, 0.0) + amount

    def log_raw_call(
        self,
        *,
        seat: str | None,
        model_key: str | None,
        purpose: str,
        attempt: int,
        system_prompt: str,
        user_prompt: str,
        response_text: str,
        error: str | None,
        cost_usd: float = 0.0,
    ) -> None:
        """Exact record of one LLM call for auditing -- verbatim input and verbatim
        raw output text, independent of whatever the engine/replay logs render.
        """
        self.raw_calls.append(
            {
                "seq": self._next_seq(),
                "day": self.day,
                "seat": seat,
                "model_key": model_key,
                "purpose": purpose,
                "attempt": attempt,
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "response_text": response_text,
                "error": error,
                "cost_usd": cost_usd,
            }
        )

    def public_transcript_text(self) -> str:
        # System events (deaths, eliminations, showdown announcements) are pulled into
        # their own leading "KEY FACTS" block instead of staying interleaved with
        # chatter -- same information, same token cost, but a model skimming a long
        # transcript sees the decision-relevant facts first instead of them being
        # diluted among dozens of discussion lines. Facts always stay in full; verbose
        # "speech" entries older than the detail window are dropped so prompt size
        # doesn't grow quadratically over a long game. If a day_summaries entry exists
        # for a dropped day (opt-in, see game/summarizer.py), one summary line stands
        # in for that day's discussion instead of losing it entirely.
        cutoff = self.day - self.transcript_full_detail_days
        facts = []
        discussion = []
        summarized_days: set[int] = set()
        for e in self.public_log:
            if e.kind == "system":
                facts.append(f"[Day {e.day}] {e.text}")
                continue
            if e.day < cutoff:
                if e.day not in summarized_days:
                    summarized_days.add(e.day)
                    summary = self.day_summaries.get(e.day)
                    if summary:
                        discussion.append(f"[Day {e.day}] Discussion summary: {summary}")
                continue
            discussion.append(f"[Day {e.day}] {e.speaker}: {e.text}")

        if not facts and not discussion:
            return "(no public events yet)"
        parts = []
        if facts:
            parts.append("KEY FACTS (deaths, eliminations, and other game events, in order):\n" + "\n".join(facts))
        if discussion:
            parts.append("DISCUSSION:\n" + "\n".join(discussion))
        return "\n\n".join(parts)

    def mafia_transcript_text(self) -> str:
        lines = []
        for e in self.mafia_log:
            lines.append(f"[Night {e.day}] {e.speaker}: {e.text}")
        return "\n".join(lines) if lines else "(no mafia chat yet)"
