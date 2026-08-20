from __future__ import annotations

from .roles import Role
from .state import GameState, Player

RULES_BLOCK = """You are playing Mafia (aka Werewolf), a social deduction game.

Roles:
- Mafia: know each other, secretly eliminate one town player each night, win when
  mafia members are >= remaining town members.
- Detective: each night learns whether one chosen player is "mafia" or "town".
- Doctor: each night protects one player from that night's mafia kill.
- Villager: no special power.
Town (detective, doctor, villagers) wins when all mafia are eliminated.

Each day, all living players discuss publicly, then vote to lynch one player.
Play strategically and in-character. Never reveal your private reasoning to
other players -- only the "message"/"target"/"vote" fields you're asked for
are ever shown to anyone else. Keep public messages concise (2-4 sentences).
"""

JSON_ONLY_NOTE = "Respond with ONLY a single JSON object, no other text, matching exactly this shape: "


def build_system_prompt(state: GameState, player: Player) -> str:
    lines = [RULES_BLOCK]
    lines.append(f"You are {player.seat}. Your secret role is: {player.role.value}.")

    if player.role == Role.MAFIA:
        teammates = [p.seat for p in state.players if p.role == Role.MAFIA and p.seat != player.seat]
        if teammates:
            lines.append(f"Your fellow mafia teammate(s): {', '.join(teammates)}.")
        else:
            lines.append("You have no surviving mafia teammates -- you're on your own.")

    if player.private_notes:
        lines.append("Your private notes from previous nights:")
        lines.extend(f"- {n}" for n in player.private_notes)

    return "\n".join(lines)


def _alive_line(state: GameState, exclude: list[str] | None = None) -> str:
    exclude = exclude or []
    names = [p.seat for p in state.alive_players() if p.seat not in exclude]
    return f"Alive players: {', '.join(names)}"


def build_day_discussion_prompt(state: GameState) -> str:
    return (
        f"{state.public_transcript_text()}\n\n"
        f"{_alive_line(state)}\n"
        "It is the day discussion phase. Share your thoughts publicly.\n"
        f'{JSON_ONLY_NOTE}{{"thought": "<private reasoning, not shown to others>", '
        '"message": "<your public statement>"}'
    )


def build_day_vote_prompt(state: GameState) -> str:
    return (
        f"{state.public_transcript_text()}\n\n"
        f"{_alive_line(state)}\n"
        "It is the voting phase. Choose one alive player to vote to lynch "
        "(you may vote for yourself only if you have no better option).\n"
        f'{JSON_ONLY_NOTE}{{"thought": "<private reasoning>", "vote": "<exact player name>"}}'
    )


def build_night_mafia_prompt(state: GameState, player: Player) -> str:
    exclude = [p.seat for p in state.players if p.role == Role.MAFIA]
    return (
        f"{state.mafia_transcript_text()}\n\n"
        f"{_alive_line(state, exclude=[])}\n"
        "It is the night phase. Discuss privately with your mafia teammate(s) and "
        "propose who to eliminate tonight. You may not target a fellow mafia member.\n"
        f'{JSON_ONLY_NOTE}{{"thought": "<private reasoning>", "message": "<what you say '
        'to your mafia teammates>", "target": "<exact player name to propose killing>"}}'
    )


def build_night_doctor_prompt(state: GameState, player: Player) -> str:
    return (
        f"{state.public_transcript_text()}\n\n"
        f"{_alive_line(state)}\n"
        "It is the night phase. Choose one alive player to protect from tonight's "
        "mafia attack (you may protect yourself).\n"
        f'{JSON_ONLY_NOTE}{{"thought": "<private reasoning>", "save": "<exact player name>"}}'
    )


def build_night_detective_prompt(state: GameState, player: Player) -> str:
    return (
        f"{state.public_transcript_text()}\n\n"
        f"{_alive_line(state, exclude=[player.seat])}\n"
        "It is the night phase. Choose one alive player (not yourself) to secretly "
        "investigate; you will learn if they are mafia or town.\n"
        f'{JSON_ONLY_NOTE}{{"thought": "<private reasoning>", "investigate": "<exact player name>"}}'
    )
