# MafiaSim

Makes chatbots (Claude, GPT, Gemini, Grok, Mistral, DeepSeek, Llama, Cohere, ...)
play Mafia/Werewolf against each other, logs full transcripts, and produces a
leaderboard to see which model is actually best at deception and deduction.

## How it works

- Each model in `config/models.yaml` is a candidate "player." A game samples N
  of them, assigns seats (`Player1`, `Player2`, ...) and secret roles (mafia /
  detective / doctor / villager per `config/game_rules.yaml`), and never tells
  players which underlying model an opponent is -- only their seat name.
- Every model is tagged with a `vendor` (the company behind it). A game never
  seats two models from the same vendor together (no Claude-vs-Claude,
  Gemini-vs-Gemini, etc.) -- it samples one distinct vendor per seat, falling
  back to an even round-robin only if there aren't enough distinct vendors to
  fill every seat.
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
A few things in `config/game_rules.yaml` are already tuned to bound spend:
`max_tokens: 350` (JSON replies don't need more), `max_days: 12` (caps the
worst case), and `transcript_full_detail_days: 3` -- older day-by-day
discussion text is dropped from the prompt (deaths/lynches and votes stay
for the whole game since they're short and strategically important), so
prompt size doesn't grow quadratically over a long game. The prompts also
instruct models to keep replies to 1-2 sentences.

## Editing the roster

`config/models.yaml` is the only place model choice lives -- add, remove, or
swap `model_id` strings there; no code changes needed. `config/game_rules.yaml`
controls role ratios, discussion rounds, tie-break policy, and LLM sampling
params.

### Alternate roster: OpenRouter

`config/models.openrouter.yaml` is a parallel roster covering the same set of
companies, but every model is routed through [OpenRouter](https://openrouter.ai)
instead of each provider's own API -- one `OPENROUTER_API_KEY`, one prepaid
balance, no per-provider billing setup. Use it with `--models`:

```
python -m mafia_sim.cli run --games 20 --players 8 --models config/models.openrouter.yaml
```

The two roster files are independent -- `config/models.yaml` (direct provider
APIs) is untouched by this and still works on its own once those providers'
keys have credit.

## Tests

```
pip install -r requirements-dev.txt
python -m pytest
```

Tests run entirely against the mock provider, so they need no API keys and
cost nothing.
