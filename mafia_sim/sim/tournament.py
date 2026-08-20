from __future__ import annotations

import random

from ..agents.player_agent import PlayerAgent
from ..game.engine import GameEngine, GameResult
from ..game.roles import build_role_setup
from ..game.state import GameState, LogEntry, Player
from ..providers.base import ChatProvider
from ..providers.factory import ModelSpec
from .logger import ResultsLogger

Roster = dict[str, tuple[ModelSpec, ChatProvider]]


def _sample_model_keys(roster: Roster, player_count: int) -> list[str]:
    """Picks player_count model keys, preferring one distinct vendor (company)
    per seat so a game never pits e.g. two Claude models, or two Gemini models,
    against each other. Falls back to an even round-robin over vendors (rather
    than plain random reuse) only if there aren't enough distinct vendors to
    give every seat a unique one.
    """
    by_vendor: dict[str, list[str]] = {}
    for key, (spec, _provider) in roster.items():
        by_vendor.setdefault(spec.vendor, []).append(key)

    vendors = list(by_vendor.keys())
    if not vendors:
        raise ValueError("roster is empty -- no models with API keys configured")

    if len(vendors) >= player_count:
        chosen_vendors = random.sample(vendors, player_count)
    else:
        base = vendors * (player_count // len(vendors))
        remainder = random.sample(vendors, player_count % len(vendors))
        chosen_vendors = base + remainder
        random.shuffle(chosen_vendors)

    chosen = [random.choice(by_vendor[v]) for v in chosen_vendors]
    random.shuffle(chosen)
    return chosen


def setup_game(
    roster: Roster, player_count: int, role_setups: dict, rules: dict, on_event=None
) -> tuple[GameState, dict[str, PlayerAgent]]:
    chosen = _sample_model_keys(roster, player_count)

    role_counts = build_role_setup(player_count, role_setups)
    role_pool = []
    for role, n in role_counts.items():
        role_pool += [role] * n
    random.shuffle(role_pool)

    seats = [f"Player{i + 1}" for i in range(player_count)]
    players: list[Player] = []
    agents: dict[str, PlayerAgent] = {}
    for seat, model_key, role in zip(seats, chosen, role_pool):
        players.append(Player(seat=seat, model_key=model_key, role=role))
        spec, provider = roster[model_key]
        agents[seat] = PlayerAgent(spec, provider, rules)

    state = GameState(
        players=players,
        transcript_full_detail_days=rules.get("transcript_full_detail_days", 3),
        on_event=on_event,
    )
    return state, agents


def run_tournament(
    roster: Roster,
    player_count: int,
    num_games: int,
    role_setups: dict,
    rules: dict,
    logger: ResultsLogger,
    on_game_done=None,
    on_event=None,
) -> list[GameResult]:
    summarizer_key = rules.get("summarizer_model")
    summarizer = roster[summarizer_key][1] if summarizer_key and summarizer_key in roster else None
    if summarizer_key and summarizer is None:
        print(f"[run] summarizer_model '{summarizer_key}' not in roster -- day summarization disabled")

    results: list[GameResult] = []
    for i in range(num_games):
        state, agents = setup_game(roster, player_count, role_setups, rules, on_event=on_event)

        if on_event:
            # Spectator-only reveal of which model is behind each seat -- sent straight
            # to the callback, never appended to state.public_log, so it never leaks
            # into what the players themselves are prompted with.
            cast = ", ".join(f"{p.seat}={roster[p.model_key][0].display_name}" for p in state.players)
            on_event(LogEntry(0, "day", "cast", None, f"Cast: {cast}"))

        engine = GameEngine(state, agents, rules, summarizer=summarizer, summarizer_key=summarizer_key)
        result = engine.run()
        game_id = logger.save_game(i, result)
        results.append(result)
        if on_game_done:
            on_game_done(i, num_games, game_id, result)
    return results
