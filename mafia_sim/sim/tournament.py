from __future__ import annotations

import random

from ..agents.player_agent import PlayerAgent
from ..game.engine import GameEngine, GameResult
from ..game.roles import build_role_setup
from ..game.state import GameState, Player
from ..providers.base import ChatProvider
from ..providers.factory import ModelSpec
from .logger import ResultsLogger

Roster = dict[str, tuple[ModelSpec, ChatProvider]]


def setup_game(
    roster: Roster, player_count: int, role_setups: dict, rules: dict
) -> tuple[GameState, dict[str, PlayerAgent]]:
    model_keys = list(roster.keys())
    if not model_keys:
        raise ValueError("roster is empty -- no models with API keys configured")

    if len(model_keys) >= player_count:
        chosen = random.sample(model_keys, player_count)
    else:
        chosen = [random.choice(model_keys) for _ in range(player_count)]
    random.shuffle(chosen)

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

    return GameState(players=players), agents


def run_tournament(
    roster: Roster,
    player_count: int,
    num_games: int,
    role_setups: dict,
    rules: dict,
    logger: ResultsLogger,
    on_game_done=None,
) -> list[GameResult]:
    results: list[GameResult] = []
    for i in range(num_games):
        state, agents = setup_game(roster, player_count, role_setups, rules)
        engine = GameEngine(state, agents, rules)
        result = engine.run()
        game_id = logger.save_game(i, result)
        results.append(result)
        if on_game_done:
            on_game_done(i, num_games, game_id, result)
    return results
