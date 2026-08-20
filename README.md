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
  phase needs: `message`/`action`, `vote`, `target`, `save`, or `investigate`.
  Malformed output is retried, then falls back to a random legal action --
  also tracked as a `format_failures` stat per model.
- Night phase: mafia privately discuss and pick a kill target by majority
  vote among themselves; doctor picks someone to protect (and learns whether
  it mattered); detective learns one player's *exact role* (not just team).
  Day phase is an open floor, not a fixed speaking order: one random player
  opens, then every alive player with messages left (max 3/day) gets tapped
  in turn to decide whether to speak, think privately, or pass -- a real
  back-and-forth, not everyone forced to talk every round. Then a **secret**
  ballot (nobody ever learns who voted for whom, only the outcome); a tie at
  the top triggers a showdown -- the tied players publicly make their case,
  then everyone revotes among just the tied set, repeating until one player
  has sole possession of the most votes. Every death is announced to the
  models simply as "died" -- no "lynched"/"killed" jargon anywhere a model
  can see it.
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

Cost note: each game makes many real API calls (day discussion polls each
alive player in turn every time it's their tap, plus votes and night
actions). Start with a small `--games`/`--players` count to gauge cost before
running a large tournament. Live cost is tracked per model and printed after
every game (and totaled at the end of a run) whenever the provider reports
it -- OpenRouter does, via `usage.cost`; the `leaderboard` command also
breaks down total/avg/per-win cost per model. `config/game_rules.yaml` has
several things tuned to bound spend:
- `max_cost_usd: 1.00` -- a hard per-game spending cap, checked between
  phases and inside the discussion/showdown loops, so one runaway game can't
  blow past it; the game just ends early as a draw if hit.
- `max_cost_share_per_model: 0.5` -- guards against one model quietly
  dominating spend (observed for real: one model, no errors, just expensive
  per token, ate ~30% of a game's total cost on its own). Same early-end
  treatment as `max_cost_usd` if any one model's cumulative cost crosses this
  fraction of the game's total spend so far.
- `max_days: 12` caps the worst case in turns.
- `discussion_silence_threshold: 6` ends a day's discussion after 6
  consecutive declines in a row rather than polling every remaining player
  every time -- the main lever against the open-floor discussion getting
  expensive on quiet days -- with one floor: nobody alive goes a whole day
  without at least one turn, even if the room "goes quiet" by this rule first.
- `transcript_full_detail_days: 3` -- older day-by-day discussion text is
  dropped from the prompt (deaths stay for the whole game since they're short
  and strategically important), so prompt size doesn't grow quadratically
  over a long game. Optionally set `summarizer_model` to a roster key to
  compress each day into one sentence instead of dropping it outright once it
  ages out of that window (costs one small extra call/day).

`max_tokens: 1400` gives room for a real private `thought` plus the JSON
structure around it -- extended-thinking models can consume much of this on
invisible reasoning tokens before writing anything visible, which is also why
this shouldn't be set too low (some models will otherwise never manage to
close their JSON at all).

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

## Viewer

Every finished game gets a self-contained `results/games/<id>.html` replay
viewer -- open it directly in a browser, no server needed. For a richer,
interactive UI there's also `viewer/`, a Next.js app that reads the same
`results/games/*.json` files:

```
cd viewer
npm install
npm run dev
```

See `viewer/README.md` for details.

## Tests

```
pip install -r requirements-dev.txt
python -m pytest
```

Tests run entirely against the mock provider, so they need no API keys and
cost nothing.
