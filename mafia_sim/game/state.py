from __future__ import annotations

from dataclasses import dataclass, field

from .roles import Role


@dataclass
class Player:
    seat: str  # e.g. "Player3" -- the only identity other players ever see
    model_key: str  # which roster entry is behind this seat (hidden from other players)
    role: Role
    alive: bool = True
    death_day: int | None = None
    death_cause: str | None = None  # "lynched" | "killed" | None
    private_notes: list[str] = field(default_factory=list)


@dataclass
class LogEntry:
    day: int
    phase: str  # "night" | "day"
    kind: str  # "system" | "speech" | "vote" | "mafia_chat"
    speaker: str | None
    text: str


@dataclass
class GameState:
    players: list[Player]
    public_log: list[LogEntry] = field(default_factory=list)
    mafia_log: list[LogEntry] = field(default_factory=list)
    day: int = 0
    day_votes: list[dict] = field(default_factory=list)  # [{day, votes: {voter: target}}]
    format_failures: dict[str, int] = field(default_factory=dict)  # model_key -> count

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

    def log_public(self, phase: str, kind: str, text: str, speaker: str | None = None) -> None:
        self.public_log.append(LogEntry(self.day, phase, kind, speaker, text))

    def log_mafia(self, kind: str, text: str, speaker: str | None = None) -> None:
        self.mafia_log.append(LogEntry(self.day, "night", kind, speaker, text))

    def note_format_failure(self, model_key: str) -> None:
        self.format_failures[model_key] = self.format_failures.get(model_key, 0) + 1

    def public_transcript_text(self) -> str:
        lines = []
        for e in self.public_log:
            if e.kind == "system":
                lines.append(f"[Day {e.day}] {e.text}")
            else:
                lines.append(f"[Day {e.day}] {e.speaker}: {e.text}")
        return "\n".join(lines) if lines else "(no public events yet)"

    def mafia_transcript_text(self) -> str:
        lines = []
        for e in self.mafia_log:
            lines.append(f"[Night {e.day}] {e.speaker}: {e.text}")
        return "\n".join(lines) if lines else "(no mafia chat yet)"
