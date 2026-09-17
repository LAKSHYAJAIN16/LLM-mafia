# MafiaSim

I wanted to know which LLM is actually best at lying and catching liars, so I built a Mafia (Werewolf) engine that makes chatbots from different companies play against each other. Claude, GPT, Gemini, Grok, Mistral, DeepSeek, Llama, Cohere -- whatever's in the roster -- get thrown into a game, given secret roles, and left to bluff, accuse, and vote each other out. Every game gets fully logged and turned into a leaderboard so I can actually see who's good at this.

## How a game works

Each model listed in `config/models.yaml` is a candidate player. A game samples N of them, gives them seat names (`Player1`, `Player2`, ...), and assigns secret roles -- mafia, detective, doctor, villager -- per `config/game_rules.yaml`. Nobody ever finds out which underlying model they're up against, only the seat name. I also tag every model with its vendor and never let two models from the same company share a game, so it's a real cross-company matchup instead of, say, Claude quietly playing itself.

Every turn is one stateless completion call: the model sees the public transcript (plus mafia-only chat if it's mafia) and its own private notes, and has to answer with strict JSON -- a private `thought` nobody else ever sees, plus whatever the phase needs (a message, a vote, a target to kill/save/investigate). If a model returns garbage JSON I retry it, then fall back to a random legal move and log it as a `format_failures` strike against that model.

Nights: mafia privately vote on a kill, the doctor picks someone to protect, the detective learns one player's exact role. Days are an open floor rather than a fixed speaking order -- one random player opens, then everyone alive with turns left gets tapped to decide whether to talk, think privately, or pass. Voting is a secret ballot (nobody ever learns who voted for whom), and ties trigger a showdown where the tied players make their case and everyone revotes among just them until it resolves. Deaths are announced as just "died" -- no "lynched" or "killed" language leaks to the models, since that would give away information they shouldn't have.

Every game gets logged in full -- transcripts, private thoughts, secret ballots, the works -- to `results/games/*.json`, plus a self-contained HTML replay you can open straight in a browser. All of that rolls up into a leaderboard with win rate (overall / as mafia / as town), a team Elo rating, how often a model got caught lying or wrongly blamed, format-failure rate, and actual dollar cost per model (via OpenRouter's live `usage.cost` when it's available).

## Setup

```
pip install -r requirements.txt
cp .env.example .env   # fill in whichever provider keys you have
```

You don't need every provider's key -- models without one configured just get skipped automatically at runtime.

## Running it

```
# sanity check with the free, no-key mock player
python -m mafia_sim.cli run --games 1 --players 8 --mock-only

# a real run once .env has keys
python -m mafia_sim.cli run --games 50 --players 8

# leaderboard from whatever's already in results/
python -m mafia_sim.cli leaderboard

# who catches whom: for every (accuser, mafia model) pair, how often does
# the accuser actually nail that model as mafia -- built from logged ballots,
# no new games needed
python -m mafia_sim.cli deception-matrix
python -m mafia_sim.cli deception-matrix --min-opportunities 10  # drop noisy pairs

# regenerate or list the HTML replay for a past game
python -m mafia_sim.cli view --list
python -m mafia_sim.cli view --game game_0000_20260101T000000Z
```

`run` streams the game live to your console (add `--quiet` for big tournaments). Every finished game also gets its own `results/games/<id>.html` replay -- full transcript, private thoughts woven in chronologically, a spoiler-gated role reveal, and play/step controls.

Fair warning on cost: a game makes a lot of real API calls (every alive player gets polled each time it's their turn to speak, plus votes and night actions). Start small before running a big tournament. Cost gets printed live per model and totaled at the end whenever the provider reports it -- OpenRouter does. A few knobs in `config/game_rules.yaml` exist specifically to keep spend sane: `max_cost_usd` hard-caps a single game (ends it as a draw if hit), `max_days` bounds the worst case in turns, `discussion_silence_threshold` cuts a day's discussion short after enough consecutive passes, and `transcript_full_detail_days` drops old day-by-day discussion from the prompt so it doesn't grow quadratically over a long game (deaths stay in, since they're short and matter strategically).

## Editing the roster

`config/models.yaml` is the only place model choice lives -- add, remove, or swap `model_id` strings, no code changes needed. `config/game_rules.yaml` controls role ratios, discussion rounds, tie-break policy, and sampling params.

There's also `config/models.openrouter.yaml`, a parallel roster covering the same companies but routed entirely through OpenRouter -- one API key, one prepaid balance, instead of setting up billing with every provider separately:

```
python -m mafia_sim.cli run --games 20 --players 8 --models config/models.openrouter.yaml
```

The two rosters don't interact -- the direct-provider one still works fine on its own if you'd rather use your own API keys.

## Viewer

Every finished game gets that self-contained HTML replay (no server needed, just open it). If you want something more interactive, `viewer/` is a separate Next.js app that reads the same `results/games/*.json` files:

```
cd viewer
npm install
npm run dev
```

See `viewer/README.md` for more on that.

## Tests

```
pip install -r requirements-dev.txt
python -m pytest
```

Tests run against a mock provider, so no API keys and no cost.
