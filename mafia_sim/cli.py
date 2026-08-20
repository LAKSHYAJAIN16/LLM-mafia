from __future__ import annotations

import argparse
import os

import yaml
from dotenv import load_dotenv

from .providers.factory import load_runnable_roster
from .sim.leaderboard import compute_leaderboard, render_markdown_table
from .sim.logger import ResultsLogger
from .sim.tournament import run_tournament

DEFAULT_MODELS_CONFIG = "config/models.yaml"
DEFAULT_RULES_CONFIG = "config/game_rules.yaml"
DEFAULT_RESULTS_DIR = "results"


def load_rules(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def cmd_run(args: argparse.Namespace) -> None:
    load_dotenv()
    rules = load_rules(args.rules)
    roster = load_runnable_roster(args.models, require_keys=not args.mock_only)

    if args.mock_only or not roster:
        if not roster:
            print("[run] no models had usable API keys -- falling back to mock-only roster")
        from .providers.factory import ModelSpec, build_provider

        mock_spec = ModelSpec(key="mock-random", display_name="Mock", provider="mock", model_id="mock-random")
        roster = {"mock-random": (mock_spec, build_provider(mock_spec))}

    print(f"[run] roster: {', '.join(roster.keys())}")

    logger = ResultsLogger(args.out)

    def on_done(i: int, total: int, game_id: str, result) -> None:
        print(f"[run] game {i + 1}/{total} ({game_id}): winner={result.winner} days={result.days}")

    run_tournament(
        roster=roster,
        player_count=args.players,
        num_games=args.games,
        role_setups=rules["role_setups"],
        rules=rules,
        logger=logger,
        on_game_done=on_done,
    )
    print(f"[run] done. Results in {args.out}/")


def cmd_leaderboard(args: argparse.Namespace) -> None:
    summary_path = os.path.join(args.results, "summary.jsonl")
    if not os.path.exists(summary_path):
        print(f"no results found at {summary_path} -- run some games first")
        return
    stats = compute_leaderboard(summary_path)
    print(render_markdown_table(stats))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mafia_sim", description="LLM Mafia game simulator")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="run one or more games and log results")
    run_p.add_argument("--games", type=int, default=1)
    run_p.add_argument("--players", type=int, default=8)
    run_p.add_argument("--models", default=DEFAULT_MODELS_CONFIG)
    run_p.add_argument("--rules", default=DEFAULT_RULES_CONFIG)
    run_p.add_argument("--out", default=DEFAULT_RESULTS_DIR)
    run_p.add_argument(
        "--mock-only", action="store_true", help="ignore API keys and use only the mock random-play model"
    )
    run_p.set_defaults(func=cmd_run)

    lb_p = sub.add_parser("leaderboard", help="print the leaderboard computed from logged results")
    lb_p.add_argument("--results", default=DEFAULT_RESULTS_DIR)
    lb_p.set_defaults(func=cmd_leaderboard)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
