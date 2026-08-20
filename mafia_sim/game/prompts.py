from __future__ import annotations

from .roles import Role
from .state import GameState, Player

RULES_BLOCK = """You are playing Mafia (aka Werewolf), a social deduction game.

Roles:
- Mafia: know each other, secretly eliminate one town player each night, win when
  mafia members are >= remaining town members.
- Detective: each night learns the exact role (mafia, detective, doctor, or
  villager) of one chosen player.
- Doctor: each night protects one player from that night's mafia kill.
- Villager: no special power.
Town (detective, doctor, villagers) wins when all mafia are eliminated.

Each day, all living players discuss publicly, then vote to eliminate one
player. Play strategically and in-character.

"thought" is your private scratchpad -- nobody else ever sees it, not even
your own future turns' prompt except as a brief note you choose to keep (see
"private notes" below, which is separate). Use it to actually reason: track
who has been inconsistent, who benefits from each death, what a lying player
would say, and what your plan is. Do not hold back here -- a few sentences
of real analysis is expected, not a one-liner.

Only the "messages"/"target"/"vote"/"save"/"investigate" field(s) you're
asked for are ever shown to anyone else, and you decide what (if anything)
of your reasoning to put in them -- you are never obligated to share your
full analysis. Keep those public-facing fields themselves short: state a
position, don't narrate your thought process.
"""

JSON_ONLY_NOTE = "Respond with ONLY a single JSON object, no other text, matching exactly this shape: "


def build_system_prompt(state: GameState, player: Player) -> str:
    lines = [RULES_BLOCK]
    lines.append(f"You are {player.seat}. Your secret role is: {player.role.value}.")

    if player.role == Role.MAFIA:
        teammates = [p for p in state.players if p.role == Role.MAFIA and p.seat != player.seat]
        alive_teammates = [p.seat for p in teammates if p.alive]
        dead_teammates = [p.seat for p in teammates if not p.alive]
        if alive_teammates:
            lines.append(f"Your fellow surviving mafia teammate(s): {', '.join(alive_teammates)}.")
        else:
            lines.append("You have no surviving mafia teammates -- you're on your own.")
        if dead_teammates:
            lines.append(
                f"Your former mafia teammate(s) who have already died: {', '.join(dead_teammates)}. "
                "Don't coordinate with them or rely on them anymore."
            )

    if player.private_notes:
        lines.append("Your private notes from previous nights:")
        lines.extend(f"- {n}" for n in player.private_notes)

    return "\n".join(lines)


def _alive_line(state: GameState, exclude: list[str] | None = None) -> str:
    exclude = exclude or []
    names = [p.seat for p in state.alive_players() if p.seat not in exclude]
    return f"Alive players: {', '.join(names)}"


def build_day_discussion_open_prompt(state: GameState) -> str:
    return (
        f"{state.public_transcript_text()}\n\n"
        f"{_alive_line(state)}\n"
        "It is the day discussion phase, and you've been randomly chosen to open it. "
        "Send one message to kick off the conversation.\n"
        f'{JSON_ONLY_NOTE}{{"thought": "<your real private analysis: a few sentences>", '
        '"message": "<one short public message>"}'
    )


def build_day_discussion_poll_prompt(state: GameState, remaining_budget: int, max_per_day: int) -> str:
    return (
        f"{state.public_transcript_text()}\n\n"
        f"{_alive_line(state)}\n"
        "Day discussion is open. This is a real back-and-forth conversation, not a "
        "fixed order -- anyone alive can jump in whenever they actually have "
        "something worth saying, and you can react to what others just said. You "
        f"have {remaining_budget} of {max_per_day} messages left today. Decide right "
        "now: do you want to speak (send exactly one short message), just think it "
        "over privately without saying anything yet, or stay silent for now? You can "
        "still speak later if you stay silent now and still have messages left.\n"
        "This is just a quick gut-check, not a full strategy session -- a brief "
        "one-line \"thought\" is fine here. Save your real multi-sentence analysis for "
        "when you actually decide to speak, vote, or act at night.\n"
        f'{JSON_ONLY_NOTE}{{"thought": "<brief one-line gut check>", '
        '"action": "speak" | "think" | "pass", '
        '"message": "<exactly one short public message -- only if action is \'speak\', omit or leave empty otherwise>"}'
    )


def build_day_vote_prompt(state: GameState) -> str:
    return (
        f"{state.public_transcript_text()}\n\n"
        f"{_alive_line(state)}\n"
        "It is the voting phase. Choose one alive player to vote to eliminate "
        "(you may vote for yourself only if you have no better option).\n"
        f'{JSON_ONLY_NOTE}{{"thought": "<your real private analysis: a few sentences>", "vote": "<exact player name>"}}'
    )


def build_day_showdown_defense_prompt(state: GameState, accused: list[str]) -> str:
    others = ", ".join(accused)
    return (
        f"{state.public_transcript_text()}\n\n"
        f"{_alive_line(state)}\n"
        f"The vote was tied between: {others}. It is now a showdown -- if you are one "
        "of the accused, make your case for why you should not be eliminated. If you "
        "are not accused, you may weigh in on the two (or more) of them instead. "
        "You may send 1 to 3 separate short messages this turn.\n"
        f'{JSON_ONLY_NOTE}{{"thought": "<your real private analysis: a few sentences>", '
        '"messages": ["<short public message>", "<optional 2nd message>", "<optional 3rd message>"]}'
    )


def build_day_showdown_vote_prompt(state: GameState, accused: list[str]) -> str:
    options = ", ".join(accused)
    return (
        f"{state.public_transcript_text()}\n\n"
        f"{_alive_line(state)}\n"
        f"Showdown revote: choose which of the tied players to eliminate ({options}).\n"
        f'{JSON_ONLY_NOTE}{{"thought": "<your real private analysis: a few sentences>", "vote": "<exact player name>"}}'
    )


def build_night_mafia_prompt(state: GameState, player: Player) -> str:
    exclude = [p.seat for p in state.players if p.role == Role.MAFIA]
    return (
        f"{state.mafia_transcript_text()}\n\n"
        f"{_alive_line(state, exclude=[])}\n"
        "It is the night phase. Discuss privately with your mafia teammate(s) and "
        "propose who to eliminate tonight. You may not target a fellow mafia member. "
        "You may send 1 to 3 separate short messages to your teammates this turn.\n"
        f'{JSON_ONLY_NOTE}{{"thought": "<your real private analysis: a few sentences>", "messages": '
        '["<message to your mafia teammates>", "<optional 2nd message>", "<optional 3rd message>"], '
        '"target": "<exact player name to propose killing>"}}'
    )


def build_night_doctor_prompt(state: GameState, player: Player) -> str:
    return (
        f"{state.public_transcript_text()}\n\n"
        f"{_alive_line(state)}\n"
        "It is the night phase. Choose one alive player to protect from tonight's "
        "mafia attack (you may protect yourself).\n"
        f'{JSON_ONLY_NOTE}{{"thought": "<your real private analysis: a few sentences>", "save": "<exact player name>"}}'
    )


def build_night_detective_prompt(state: GameState, player: Player) -> str:
    return (
        f"{state.public_transcript_text()}\n\n"
        f"{_alive_line(state, exclude=[player.seat])}\n"
        "It is the night phase. Choose one alive player (not yourself) to secretly "
        "investigate; you will learn their exact role.\n"
        f'{JSON_ONLY_NOTE}{{"thought": "<your real private analysis: a few sentences>", "investigate": "<exact player name>"}}'
    )
