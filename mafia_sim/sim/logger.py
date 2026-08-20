from __future__ import annotations

import dataclasses
import json
import os
from datetime import datetime, timezone

from ..game.engine import GameResult
from .html_report import render_game_html


class ResultsLogger:
    def __init__(self, results_dir: str):
        self.results_dir = results_dir
        self.games_dir = os.path.join(results_dir, "games")
        os.makedirs(self.games_dir, exist_ok=True)
        self.summary_path = os.path.join(results_dir, "summary.jsonl")

    def html_path(self, game_id: str) -> str | None:
        path = os.path.join(self.games_dir, f"{game_id}.html")
        return path if os.path.exists(path) else None

    def save_game(self, game_index: int, result: GameResult) -> str:
        state = result.state
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        game_id = f"game_{game_index:04d}_{timestamp}"

        full_record = {
            "game_id": game_id,
            "winner": result.winner,
            "days": result.days,
            "players": [dataclasses.asdict(p) for p in state.players],
            "public_log": [dataclasses.asdict(e) for e in state.public_log],
            "mafia_log": [dataclasses.asdict(e) for e in state.mafia_log],
            "thought_log": [dataclasses.asdict(e) for e in state.thought_log],
            "vote_log": [dataclasses.asdict(e) for e in state.vote_log],
            "day_votes": state.day_votes,
            "day_summaries": state.day_summaries,
            "format_failures": state.format_failures,
            "cost_usd": state.cost_usd,
            "total_cost_usd": round(sum(state.cost_usd.values()), 6),
        }
        with open(os.path.join(self.games_dir, f"{game_id}.json"), "w", encoding="utf-8") as f:
            json.dump(full_record, f, indent=2, default=str)

        with open(os.path.join(self.games_dir, f"{game_id}.html"), "w", encoding="utf-8") as f:
            f.write(render_game_html(full_record))

        # Exact (system_prompt, user_prompt) -> raw response text for every single LLM
        # call in the game (every retry attempt included), independent of how the
        # engine/replay logs choose to render things -- one JSON object per line.
        with open(os.path.join(self.games_dir, f"{game_id}.raw.jsonl"), "w", encoding="utf-8") as f:
            for call in sorted(state.raw_calls, key=lambda c: c["seq"]):
                f.write(json.dumps(call, default=str) + "\n")

        summary_record = {
            "game_id": game_id,
            "winner": result.winner,
            "days": result.days,
            "player_count": len(state.players),
            "players": [
                {
                    "seat": p.seat,
                    "model_key": p.model_key,
                    "role": p.role.value,
                    "team": p.role.team,
                    "alive": p.alive,
                    "death_day": p.death_day,
                    "death_cause": p.death_cause,
                }
                for p in state.players
            ],
            "format_failures": state.format_failures,
            "cost_usd": state.cost_usd,
            "total_cost_usd": round(sum(state.cost_usd.values()), 6),
        }
        with open(self.summary_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(summary_record, default=str) + "\n")

        return game_id
