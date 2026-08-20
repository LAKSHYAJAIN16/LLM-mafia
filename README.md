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
  must respond with a strict JSON object -- a private `thought` (real, unrestricted
  reasoning that no other player ever sees) plus whatever public field the
  phase needs: `messages` (1-3 short chat-style messages), `vote`, `target`,
  `save`, or `investigate`. Malformed output is retried, then falls back to a
  random legal action -- also tracked as a `format_failures` stat per model.
- Night phase: mafia privately discuss and pick a kill target by majority
  vote among themselves; doctor picks someone to protect; detective learns
  one player's *exact role* (not just team). Day phase: public discussion
  round(s), then a vote to eliminate one player. Every death is announced to
  the models simply as "died" -- no "lynched"/"killed" jargon anywhere a
  model can see it.
- Results are logged per-game (`results/games/*.json` full transcripts --
  including every private `thought` and, if a summarizer is configured, each
  day's digest -- plus `results/games/*.html`, a self-contained replay viewer,
  and `results/summary.jsonl` compact rows) and aggregated into a leaderboard
  with win rate (overall / as mafia / as town), a team-based Elo rating, how
  often a model got caught while lying (mafia) or blamed while innocent
  (town), format-failure rate, and $ cost (exact, via OpenRouter's live
  `usage.cost` where available).

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

# (re)generate the HTML replay viewer for a past game, or list game ids
python -m mafia_sim.cli view --list
python -m mafia_sim.cli view --game game_0000_20260101T000000Z
```

`run` streams the game live to the console turn-by-turn by default (pass
`--quiet` to suppress this for big tournaments). Every finished game also
gets a self-contained `results/games/<id>.html` replay viewer -- shows the
full transcript with each player's private `thought` interleaved in true
chronological order, a spoiler-gated cast/role reveal, and step-through/play
controls to watch it unfold turn by turn; open it directly in a browser.

Cost note: each game makes many real API calls (one per player per
discussion round, plus votes and night actions). Start with a small
`--games`/`--players` count to gauge cost before running a large tournament.
Live cost is tracked per model and printed after every game (and totaled at
the end of a run) whenever the provider reports it -- OpenRouter does, via
`usage.cost`; the `leaderboard` command also breaks down total/avg/per-win
cost per model. A few things in `config/game_rules.yaml` are already tuned to
bound spend: `max_days: 12` (caps the worst case) and
`transcript_full_detail_days: 3` -- older day-by-day discussion text is
dropped from the prompt (deaths and votes stay for the whole game since
they're short and strategically important), so prompt size doesn't grow
quadratically over a long game. Optionally set `summarizer_model` to a
roster key to compress each day into one sentence instead of dropping it
outright once it ages out of that window (costs one small extra call/day).
`max_tokens: 500` gives room for a real private `thought` -- the model's
actual private reasoning space, unrestricted, and never shown to other
players.

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
