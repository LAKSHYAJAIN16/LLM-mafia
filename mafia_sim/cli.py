from __future__ import annotations

import argparse
import glob
import json
import os
import sys

import yaml
from dotenv import load_dotenv

from .providers.factory import filter_roster_by_vendor, load_runnable_roster
from .sim.deception_matrix import compute_deception_matrix, hint_table
from .sim.deception_matrix import render_aggregate_table as render_deception_aggregate
from .sim.deception_matrix import render_markdown_table as render_deception_matrix
from .sim.html_report import render_game_html
from .sim.leaderboard import compute_leaderboard, render_markdown_table
from .sim.logger import ResultsLogger
from .sim.tournament import run_tournament

DEFAULT_MODELS_CONFIG = "config/models.yaml"
DEFAULT_RULES_CONFIG = "config/game_rules.yaml"
DEFAULT_RESULTS_DIR = "results"


def load_rules(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _print_event(entry) -> None:
    if entry.kind == "cast":
        print(f"\n=== {entry.text} ===\n")
    elif entry.kind == "system":
        print(f"\n[Day {entry.day}] * {entry.text}")
    elif entry.kind == "speech":
        print(f"[Day {entry.day}] {entry.speaker}: {entry.text}")
    elif entry.kind == "vote":
        print(f"[Day {entry.day}]   -> {entry.text}")
    elif entry.kind == "mafia_chat":
        print(f"[Night {entry.day}] (mafia) {entry.speaker}: {entry.text}")
    elif entry.kind == "thought":
        print(f"[Day {entry.day}]     ({entry.speaker} thinking) {entry.text}")
    elif entry.kind == "reveal":
        print(f"[Night {entry.day}]   ** {entry.text}")
    else:
        print(f"[Day {entry.day}] {entry.text}")


def _load_deception_hints(results_dir: str, min_opportunities: int) -> dict[tuple[str, str], tuple[float, int]]:
    """Aggregates whatever games are already logged under results_dir into a hint table.
    Called once, before a new tournament starts, so hints only ever reflect prior games --
    never the game currently being played.
    """
    games_dir = os.path.join(results_dir, "games")
    paths = sorted(glob.glob(os.path.join(games_dir, "*.json")))
    games = []
    for p in paths:
        with open(p, "r", encoding="utf-8") as f:
            games.append(json.load(f))
    matrix = compute_deception_matrix(games)
    return hint_table(matrix, min_opportunities=min_opportunities)


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

    if args.vendor:
        roster = filter_roster_by_vendor(roster, args.vendor)
        if not roster:
            print(f"[run] no enabled models found for vendor '{args.vendor}' -- aborting")
            return

    print(f"[run] roster: {', '.join(roster.keys())}")

    deception_hints: dict[tuple[str, str], tuple[float, int]] = {}
    if rules.get("opponent_aware_deception"):
        deception_hints = _load_deception_hints(args.out, rules.get("opponent_aware_min_opportunities", 5))
        print(f"[run] opponent-aware deception ON -- {len(deception_hints)} accuser/deceiver pair(s) with hints")

    logger = ResultsLogger(args.out)
    running_total = {"cost": 0.0}

    def on_done(i: int, total: int, game_id: str, result) -> None:
        game_cost = sum(result.state.cost_usd.values())
        running_total["cost"] += game_cost
        print(
            f"[run] game {i + 1}/{total} ({game_id}): winner={result.winner} days={result.days} "
            f"cost=${game_cost:.4f} (running total ${running_total['cost']:.4f})"
        )
        html_path = logger.html_path(game_id)
        if html_path:
            print(f"[run] replay viewer: {html_path}")

    run_tournament(
        roster=roster,
        player_count=args.players,
        num_games=args.games,
        role_setups=rules["role_setups"],
        rules=rules,
        logger=logger,
        on_game_done=on_done,
        on_event=None if args.quiet else _print_event,
        deception_hints=deception_hints,
    )
    print(f"[run] done. Results in {args.out}/. Total spend: ${running_total['cost']:.4f}")


def cmd_view(args: argparse.Namespace) -> None:
    games_dir = os.path.join(args.results, "games")
    if args.list or not args.game:
        paths = sorted(glob.glob(os.path.join(games_dir, "*.json")))
        if not paths:
            print(f"no games found in {games_dir}")
            return
        for p in paths:
            print(os.path.splitext(os.path.basename(p))[0])
        return

    json_path = os.path.join(games_dir, f"{args.game}.json")
    if not os.path.exists(json_path):
        print(f"no such game: {json_path}")
        return
    with open(json_path, "r", encoding="utf-8") as f:
        record = json.load(f)
    html_path = os.path.join(games_dir, f"{args.game}.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(render_game_html(record))
    print(f"replay viewer: {html_path}")


def cmd_leaderboard(args: argparse.Namespace) -> None:
    summary_path = os.path.join(args.results, "summary.jsonl")
    if not os.path.exists(summary_path):
        print(f"no results found at {summary_path} -- run some games first")
        return
    stats = compute_leaderboard(summary_path)
    print(render_markdown_table(stats))


def cmd_deception_matrix(args: argparse.Namespace) -> None:
    games_dir = os.path.join(args.results, "games")
    paths = sorted(glob.glob(os.path.join(games_dir, "*.json")))
    if not paths:
        print(f"no games found in {games_dir} -- run some games first")
        return
    games = []
    for p in paths:
        with open(p, "r", encoding="utf-8") as f:
            games.append(json.load(f))
    matrix = compute_deception_matrix(games)
    print(f"Cross-vendor deception-asymmetry matrix, built from {len(games)} logged game(s):\n")
    if args.aggregate:
        print(render_deception_aggregate(matrix))
    else:
        print(render_deception_matrix(matrix, min_opportunities=args.min_opportunities))


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
    run_p.add_argument(
        "--quiet", action="store_true", help="suppress live turn-by-turn output (recommended for big tournaments)"
    )
    run_p.add_argument(
        "--vendor",
        default=None,
        help="restrict the roster to a single vendor (e.g. 'anthropic') for a same-vendor control game",
    )
    run_p.set_defaults(func=cmd_run)

    lb_p = sub.add_parser("leaderboard", help="print the leaderboard computed from logged results")
    lb_p.add_argument("--results", default=DEFAULT_RESULTS_DIR)
    lb_p.set_defaults(func=cmd_leaderboard)

    dm_p = sub.add_parser(
        "deception-matrix",
        help="print the cross-vendor deception-asymmetry matrix (which models fool which)",
    )
    dm_p.add_argument("--results", default=DEFAULT_RESULTS_DIR)
    dm_p.add_argument(
        "--min-opportunities", type=int, default=1, help="hide accuser/deceiver pairs with fewer data points"
    )
    dm_p.add_argument(
        "--aggregate",
        action="store_true",
        help="print per-deceiver aggregate detectability (summed over all accusers) instead of the pairwise table",
    )
    dm_p.set_defaults(func=cmd_deception_matrix)

    view_p = sub.add_parser("view", help="(re)generate the HTML replay viewer for a logged game")
    view_p.add_argument("--game", help="game_id, e.g. game_0000_20260101T000000Z")
    view_p.add_argument("--list", action="store_true", help="list available game ids")
    view_p.add_argument("--results", default=DEFAULT_RESULTS_DIR)
    view_p.set_defaults(func=cmd_view)

    return parser


def main() -> None:
    # Some roster models (Chinese-vendor ones especially) can produce native-script
    # text in a "thought" or public message. Windows' default console encoding
    # (cp1252 here) can't represent arbitrary Unicode and crashes the whole process
    # on print() instead of just garbling that one line -- force UTF-8 output, with
    # a safe fallback so even a character UTF-8-capable terminals still can't render
    # never takes the whole run down mid-game.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
