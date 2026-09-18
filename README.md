# MafiaSim

> Pit LLMs from different companies against each other in a game of Mafia, then rank who's best at lying and catching liars.

MafiaSim is a Mafia (Werewolf) engine where models from different companies play as anonymous seats, get secret roles, and vote each other out. Every game is fully logged into a leaderboard with win rate, Elo, lie-detection stats, and cost per model -- the point is finding out which model actually bluffs and reads bluffs best.

## How it works
- Models come from `config/models.yaml`; a game samples N of them, never two from the same company
- Each turn is a stateless completion call returning strict JSON (a private thought + whatever move the phase needs)
- Bad JSON gets retried, then falls back to a random legal move logged as a strike
- Nights: mafia vote to kill, doctor protects, detective investigates
- Days: open-floor discussion, then a secret ballot; ties trigger a revote showdown among the tied players
- Every game logs to `results/games/*.json` plus a self-contained HTML replay

## Setup
```
pip install -r requirements.txt
cp .env.example .env   # fill in whichever provider keys you have
```
Models without a configured key are skipped automatically at runtime.

## Running it
```
python -m mafia_sim.cli run --games 1 --players 8 --mock-only   # sanity check, no keys needed
python -m mafia_sim.cli run --games 50 --players 8              # real run
python -m mafia_sim.cli leaderboard
python -m mafia_sim.cli deception-matrix                        # who catches whom, from logged ballots
python -m mafia_sim.cli view --list
python -m mafia_sim.cli view --game game_0000_20260101T000000Z
```
Add `--quiet` to `run` for big tournaments. Cost is printed live per model and capped per game via `max_cost_usd` in `config/game_rules.yaml`.

## Roster & rules
`config/models.yaml` controls which models play -- add, remove, or swap `model_id`, no code changes needed. `config/game_rules.yaml` controls role ratios, discussion rounds, tie-break policy, and cost/length limits. `config/models.openrouter.yaml` is an alternate roster covering the same companies routed entirely through OpenRouter, so one key instead of per-provider billing.

## Viewer
`viewer/` is a separate Next.js app for browsing `results/games/*.json` interactively (the per-game HTML replay needs no server):
```
cd viewer
npm install
npm run dev
```

## Tests
```
pip install -r requirements-dev.txt
python -m pytest
```
Runs against a mock provider -- no API keys, no cost.
