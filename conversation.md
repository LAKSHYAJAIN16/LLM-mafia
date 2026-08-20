# Building MafiaSim: conversation summary

Goal: build a simulator where different LLM chatbots (Claude, GPT, Gemini, Grok,
Mistral, DeepSeek, Llama, Qwen, Cohere, and others) play Mafia/Werewolf against
each other, so we can see empirically which model is actually best at
deception, deduction, and persuasion.

## Architecture

- **Provider adapters** (`mafia_sim/providers/`): raw `requests` HTTP calls, no
  provider SDKs. One adapter each for Anthropic's native API and Google's
  native Gemini API (different request/response shapes), plus a generic
  `OpenAICompatProvider` that covers any OpenAI-style `/chat/completions`
  endpoint (OpenAI, xAI, Mistral, DeepSeek, Groq, Cohere, and OpenRouter).
- **Game engine** (`mafia_sim/game/`): classic Mafia rules -- night phase
  (mafia coordinate privately and pick a kill by majority vote, doctor
  protects, detective investigates), day phase (discussion round(s), then a
  vote). Every turn is one stateless completion call; the model returns a
  strict JSON object with a private `thought` and whatever public field the
  phase needs.
- **Roster diversity**: every model is tagged with a `vendor` (the company
  behind it). A game samples one distinct vendor per seat, so it never seats
  two models from the same company together (no Claude-vs-Claude, etc.),
  falling back to an even round-robin only if there aren't enough distinct
  vendors to fill every seat.
- **Two roster configs**: `config/models.yaml` (each provider's own direct
  API, own billing) and `config/models.openrouter.yaml` (everything routed
  through one OpenRouter key/balance instead). Independent and interchangeable
  via `--models`.
- **Leaderboard**: win rate (overall / as mafia / as town), a team-based Elo
  rating, detection rate (how often a model got caught while lying as mafia),
  friendly-fire rate (how often it got wrongly voted out as town），
  format-failure rate, and $ cost (total / per-game / per-win).
- **HTML replay viewer**: every finished game gets a self-contained
  `results/games/<id>.html` -- a spoiler-gated cast/role/outcome table, the
  full transcript with each player's private `thought` interleaved in true
  chronological order (a global `seq` counter merges the public, mafia-only,
  and thought logs correctly), and step-through/play controls.
- **Live streaming**: `run` prints the game to the console turn-by-turn by
  default (`--quiet` to suppress), including a spectator-only cast reveal
  that's never leaked into what the models themselves are prompted with.

## Key decisions and fixes made along the way

- **Model roster & verification**: proposed a 12+ model roster across 7+
  companies; every model ID was live-verified against each provider's actual
  API (several of the initially-guessed IDs, like `gpt-5.1`, didn't exist --
  the real current models were `gpt-5.5` / `gpt-5.4-mini`, etc.). Config is
  just YAML, so IDs can be corrected without touching code.
- **OpenRouter as a parallel path**: rather than requiring separate billing
  setup on 7+ provider dashboards, added `config/models.openrouter.yaml` so
  the whole roster (15 models, including open-weight ones like Qwen, Kimi K2,
  and GLM) runs through one funded key. Verified all 15 model slugs with real
  completion calls before relying on them.
- **A real UTF-8 corruption bug**: the first live game revealed em dashes and
  curly quotes turning into literal `U+FFFD` replacement characters in stored
  transcripts. Root cause: `requests`' automatic encoding-detection guessed
  wrong for some responses. Fixed by decoding response bytes as UTF-8
  explicitly in every provider adapter instead of trusting `requests`' guess,
  with a regression test that reproduces the exact corruption mechanism.
- **Reasoning depth**: the private `"thought"` field was initially capped at
  "one short sentence" for cost control, which visibly hurt play quality
  (shallow, generic discussion). Rewritten so `thought` is an explicit,
  unrestricted private scratchpad ("a few sentences of real analysis
  expected"), while the public-facing field the model chooses to share stays
  short. This was the single biggest quality lever -- confirmed players now
  reason through motive, behavioral patterns, and lie-detection in `thought`
  before deciding what (if anything) to say publicly.
- **Detective upgraded**: now learns a target's *exact role*, not just team
  (mafia/town) -- makes town's information asymmetric enough to fight back
  against a well-played mafia.
- **Multi-message turns**: players can send 1-3 short messages per turn
  (like a real chat burst) instead of one monolithic statement, with no extra
  API call cost -- one completion call still returns a list.
- **No Mafia jargon reaches the models or the reports**: "lynch"/"lynched"
  removed everywhere -- prompts say "vote to eliminate", every death is
  announced as simply "died", and the internal `death_cause` value is
  `voted_out` (renamed from `lynched`) so it never surfaces the word anywhere
  a model or a report can see it. (Nothing stops a model from using the word
  "lynch" unprompted in its own free-form output -- that's the model's own
  vocabulary, not something we feed it.)
- **Cost tracking**: OpenRouter reports the exact USD cost of each generation
  via `usage.cost` when asked (`usage: {include: true}`); this is captured
  per call, accumulated per model per game, printed live during a run (with a
  running total), and broken out in the leaderboard (total / avg / per-win).
  Direct-API providers get an optional static price-table fallback for models
  without live cost reporting.
- **Context minimization, researched not guessed**: asked to look into
  token/context-minimization strategies (prompt caching, "VecDBs, or
  something"). Researched current practice: prompt caching (Anthropic
  `cache_control` breakpoints for a 90% discount on cache reads, OpenAI's
  automatic prefix caching, Gemini's implicit/explicit caching) is a pure
  win worth applying later. For context size, RAG/vector retrieval is
  designed for corpora large enough that *selecting* beats *holding
  everything* -- our worst-case transcript (~12 days, 8 players, short
  messages) is only a few thousand tokens, well under that threshold. Went
  with the validated approach for this scale instead: a sliding window
  (`transcript_full_detail_days`, already in place) plus an opt-in
  **day-summarizer** -- a dedicated model (never one under evaluation) that
  compresses a day's discussion into one sentence once it ages out of the
  prompt window, instead of silently dropping it. Off by default since it's
  an extra real API call.
- **Private thoughts were being discarded**: originally only used in-memory
  to decide the model's action, then thrown away. Now persisted to a
  spectator-only `thought_log`, verified structurally unreachable from
  anything that builds a model's prompt (confirmed on request: `thought_log`
  is only ever appended to; `public_transcript_text()` /
  `mafia_transcript_text()`, the only functions that build prompts, read
  exclusively from `public_log`/`mafia_log`).

## First real game (OpenRouter roster, 8 players)

Cast: DeepSeek Chat, Mistral Large, GPT-5.5, Gemini 3.6 Flash, Kimi K2, Llama
3.3 70B, Cohere Command A, Claude Sonnet 5 -- one from each of 8 different
companies.

- **Mafia**: DeepSeek Chat + GPT-5.5. **Detective**: Kimi K2. **Doctor**: Llama
  3.3 70B.
- Night 1: mafia killed Gemini 3.6 Flash (a villager). Detective investigated
  and correctly identified the mafia player.
- Day 1: town voted out DeepSeek Chat (correct -- one mafia down). The mafia
  member actually voted for themselves in an apparent bandwagon/misdirection
  attempt; didn't matter, the majority already had it.
- Night 2: surviving mafia (GPT-5.5) killed the doctor (Llama 3.3 70B).
- Day 2: detective publicly claimed and named both mafia players by seat.
  GPT-5.5 tried a last-ditch counter-accusation against the detective, but
  town believed the claim and voted GPT-5.5 out.
- **Result: Town wins**, both mafia identified and eliminated, zero
  mislynches. Two format-failure fallbacks fired (GPT-5.5, Claude Sonnet 5)
  and were handled gracefully by the retry/fallback mechanism. Total cost:
  **$0.2733** (GPT-5.5 alone was ~61% of that, being the priciest flagship
  model and also mafia, meaning more calls).

## Current state

- 19 tests passing, all against the free mock provider (no API cost to run
  the suite).
- Repo: https://github.com/LAKSHYAJAIN16/LLM-mafia
- Games only run when explicitly requested -- this simulator makes real,
  metered API calls.
