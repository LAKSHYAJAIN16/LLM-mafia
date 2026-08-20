# MafiaSim

Makes chatbots (Claude, GPT, Gemini, Grok, Mistral, DeepSeek, Llama, Cohere, ...)
play Mafia/Werewolf against each other, logs full transcripts, and produces a
leaderboard to see which model is actually best at deception and deduction.

## How it works

- Each model in `config/models.yaml` is a candidate "player." A game samples N
  of them, assigns seats (`Player1`, `Player2`, ...) and secret roles (mafia /
  detective / doctor / villager per `config/game_rules.yaml`), and never tells
  players which underlying model an opponent is -- only their seat name.
- Every turn is a single stateless completion call: the model gets the public
  transcript (and mafia-only chat, if it's mafia) plus its private notes, and
  must respond with a strict JSON object (a private `thought` plus whatever
  public field the phase needs: `message`, `vote`, `target`, `save`, or
  `investigate`). Malformed output is retried, then falls back to a random
  legal action -- also tracked as a `format_failures` stat per model.
- Night phase: mafia privately discuss and pick a kill target by majority
  vote among themselves; doctor picks someone to protect; detective learns
  one player's team. Day phase: public discussion round(s), then a vote,
  then a lynch.
- Results are logged per-game (`results/games/*.json` full transcripts,
  `results/summary.jsonl` compact rows) and aggregated into a leaderboard
  with win rate (overall / as mafia / as town), a team-based Elo rating,
  how often a model got caught while lying (mafia) or blamed while innocent
  (town), and format-failure rate.

## Setup

```
pip install -r requirements.txt
cp .env.example .env   # fill in whichever provider keys you have
```

Models without a key set are skipped automatically at runtime -- you don't
need all of them to start.

## Running

```
# single game, using only the free no-key mock player (sanity check)
python -m mafia_sim.cli run --games 1 --players 8 --mock-only

# real run once you've added API keys to .env
python -m mafia_sim.cli run --games 50 --players 8

# print the leaderboard from whatever's in results/ so far
python -m mafia_sim.cli leaderboard
```

Cost note: each game makes many real API calls (one per player per
discussion round, plus votes and night actions). Start with a small
`--games`/`--players` count to gauge cost before running a large tournament.

## Editing the roster

`config/models.yaml` is the only place model choice lives -- add, remove, or
swap `model_id` strings there; no code changes needed. `config/game_rules.yaml`
controls role ratios, discussion rounds, tie-break policy, and LLM sampling
params.

## Tests

```
pip install -r requirements-dev.txt
python -m pytest
```

Tests run entirely against the mock provider, so they need no API keys and
cost nothing.
