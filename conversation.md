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

## Second session: secret ballots, tie showdowns, lazy summarization, raw I/O log

- **Secret voting**: votes used to be written straight into `public_log`, so
  every voter after the first could literally read who everyone before them
  had voted for in that same round -- and it stayed visible in all later
  prompts too. Fixed by giving votes their own spectator-only `vote_log`
  (mirrors how private `thought`s already worked), so `public_transcript_text()` --
  the only thing that ever builds a player's prompt -- never contains a vote.
  The HTML replay still shows every vote to spectators, just sourced from
  `vote_log` instead of `public_log`.
- **Tie showdowns**: a tied day-vote used to be resolved by an immediate
  coin-flip (or `no_elimination`). Now a tie triggers a showdown -- the tied
  players get a public turn to make their case, then *everyone* revotes with
  choices narrowed to just the tied set, repeating until one player has sole
  possession of the top vote count. Bounded by `max_showdown_rounds` (default
  5, in `config/game_rules.yaml`); `tie_vote_policy` is now only the fallback
  if a tie survives that many rounds.
- **Summarizer fixed to be lazy**: the opt-in day-summarizer was firing every
  single day regardless of whether `transcript_full_detail_days` actually
  needed it yet -- burning a real API call on day 2 of a 3-day window for no
  reason. Now it only summarizes the one day that's about to age out of the
  window, right when that's about to happen, matching what the docstring
  always claimed it did. Still off by default (`summarizer_model: null`).
- **Raw model I/O log**: added a new per-game `games/<id>.raw.jsonl` --
  distinct from the curated `.json`/`.html` replay -- with one line per LLM
  call (every retry attempt included) recording the *exact* `system_prompt`,
  `user_prompt`, and verbatim `response_text` sent/received, tagged with
  `seat`, `model_key`, and a `purpose` (`night_mafia`, `day_vote`,
  `day_showdown_defense`, `day_summary`, etc.). Written by
  `GameState.log_raw_call`, called from every `PlayerAgent.ask()` attempt and
  from the summarizer call site.
- Verified all of the above with a real mock-only 8-player run: a genuine tie
  occurred, triggered a showdown, resolved via revote, and no vote ever
  leaked into the public transcript.

## Real game #2 (OpenRouter, 8 players) -- showdown fires for real

Cast: Mistral Large, Kimi K2, Cohere Command A, DeepSeek Chat, Grok 4.6,
Llama 3.3 70B, Gemini 2.5 Pro, Qwen 2.5 72B.

- Night 1 killed a villager; day 1 voted out another villager (no tie).
  Night 2 killed a villager; day 2 correctly caught one mafia (Qwen).
- **Day 3 produced a genuine 2-2 tie** between the detective and a villager --
  the showdown mechanic fired for the first time in a real game: both got a
  public defense turn, then a revote resolved it 3-1, eliminating the
  detective (an unlucky mislynch, not a bug -- confirmed correct behavior).
- Surviving mafia (Kimi K2) rode it to parity and won on night 4.
- **Result: mafia wins**, 4 days, **$0.1803**, 20 secret votes recorded with
  zero leaking into the transcript, 67 raw calls logged, 2 real format-failure
  retries (Gemini 2.5 Pro, Mistral Large) handled gracefully.

## Investigating Gemini 2.5 Pro, plus three real bugs found from real play

User flagged: Gemini 2.5 Pro "never responds," wanted fuller live monitoring,
suspected the bots don't really understand doctor/detective, and noticed a
mafia member acting like it didn't know its teammate had died.

- **Gemini 2.5 Pro root cause found, not just "swap the model"**: pulled
  `games/<id>.raw.jsonl` and found every single response was 44-82 characters
  vs. 300-2200 for every other model in the same game. Its extended-thinking
  tokens count against `max_tokens` on OpenRouter's unified endpoint, so
  almost the whole budget was invisible reasoning, leaving ~15-20 visible
  tokens -- never enough to close the JSON. Disabled it in
  `config/models.openrouter.yaml` (`gemini-3.6-flash-or`, unaffected, still
  covers the Google seat); this is the same reason `max_tokens` went 500 ->
  1400 in `game_rules.yaml` game-wide, since any reasoning-heavy model can hit
  this.
- **Real bug: mafia didn't know a teammate had died.** `build_system_prompt`
  listed mafia teammates by role membership only, with no `alive` filter --
  a lone surviving mafia player's system prompt kept saying "your teammate is
  Player X" forever after X was voted out. Fixed to split alive vs. dead
  teammates with an explicit "already died" note (`mafia_sim/game/prompts.py`).
- **Doctor had no save feedback; detective's was fine.** The detective
  already got an exact-role private note per investigation. The doctor picked
  someone to protect and never learned whether it mattered. Added the same
  kind of note: "you protected X -- they were attacked and you saved them!"
  or "No attack landed on them that night" (`mafia_sim/game/engine.py`).
- **Day-summarization wasn't actually failing** -- it's opt-in
  (`summarizer_model: null`) and simply never ran in the first real game
  (4 days, 3-day window, nothing ever aged out). The "context feels off"
  impression was really the mafia-teammate bug above.

## Real game #3 (OpenRouter, 10 players) -- verifying the fixes live

Cast: DeepSeek Chat, Kimi K2, Claude Haiku 4.5, Llama 3.3 70B, GPT-5.5,
GLM-4.6, Cohere Command A, Mistral Large, Grok 4.6, Gemini 3.6 Flash.
Monitored with a wider live filter this time (day speech + mafia night-chat
included, not just system/vote/cast events), full console output also teed
to a log file.

- Mafia (Kimi K2, GLM-4.6, Cohere Command A) killed a villager night 1. Town
  correctly voted out Kimi K2 day 1 (6/9) after another player called out its
  suspiciously eager, unprompted rush to assign blame.
- **Confirmed the mafia-teammate-death fix working live**: the surviving
  mafia's own night-2 chat opened with "Player2 is out, so it's just us two
  now" -- correct real-time awareness instead of the old bug.
- Mafia killed another villager night 2; town correctly voted out GLM-4.6
  day 2 (6/7) after its silence under direct pressure became the read.
  One villager was mislynched day 3 (still town-favored at that point).
  Down to 1 mafia (Cohere Command A) vs. 2 town, the doctor (Mistral Large)
  openly claimed to build trust, and the town correctly voted out the last
  mafia day 4, 2-1, for a clean **town win**. $0.3289 total.
- **Investigated two things flagged live, both resolved**:
  - Mojibake (`shouldn't` rendering as `shouldn�t`) seen in the live console
    turned out to be a Windows console codepage display artifact only --
    confirmed zero `U+FFFD` characters in the actual saved `.json`/`.raw.jsonl`
    data. Not a data bug; the earlier UTF-8 decode fix is still holding.
  - Two real format-failure clusters, found via the raw log: GLM-4.6 returned
    completely empty content (0 chars, HTTP 200, no error) on every attempt
    across two separate turns, even at `max_tokens=1400` -- same failure class
    as Gemini 2.5 Pro, just total starvation instead of partial. Disabled it
    too. Grok 4.6 hit a genuine transient `502` ("model is currently at
    capacity") from xAI -- a real provider outage, not a bug, and likely what
    caused a multi-minute live-monitoring stall while it exhausted retries.
  - While fixing this, found and fixed a related latent bug: `OpenAICompatProvider`
    now flags a syntactically-valid-but-empty `message.content` as
    `error="empty_completion"` instead of silently treating it as success, so
    it's self-explanatory in `raw.jsonl` without checking response length by
    hand. `PlayerAgent._track_cost` also now runs *before* the error-continue
    check, since a provider still bills for an empty-but-real completion --
    the old order would have silently undercounted spend for exactly this
    case.

## Persistent multi-turn chat: researched, not built

Asked whether players could talk to their model like a continuous chat session
instead of resending context every call. Answer given: no provider actually
lets a model "remember" for free -- every request is stateless and the full
context has to be resent regardless (that's true even of chatgpt.com/claude.ai;
the website reconstructs the whole conversation every message). What *is* real
and worth having eventually is prompt caching on a per-player growing message
array (flagged as "a pure win" in an earlier session, never built) -- but that's
a genuine architecture change (`ChatProvider.complete()` is a flat one-shot
system+user call by design) with its own hard problem (the sliding-window +
summarizer trick that bounds prompt growth today doesn't retrofit cleanly onto
a persistent array you can't edit old turns out of). Shelved for later, not
implemented.

## Open-floor day discussion, then made it cheaper and more human

First pass: replaced the fixed round-robin day discussion (every alive player
forced to send 1-3 messages every round) with a real open floor -- one random
player opens each day, then every alive player with a daily budget of 3
messages gets polled each turn on whether to **speak** (one message), **think**
privately, or **pass**; the model chooses. Ends once the room goes quiet.
Verified end-to-end via mock game: message counts varied naturally per player
per day (0-3), the cap held exactly.

User's reaction: should feel human, and it costs more (flagged proactively --
polling everyone who stays silent is a real API call every time). Two fixes,
both aimed at the same root cause:
- **Turn-taking, not a full sweep**: was asking every remaining candidate in
  shuffled order each round until someone said yes (worst case: everyone
  passes, that's N wasted calls right at the tail of every day). Changed to
  tap exactly one player per turn, fairly cycling through everyone (a reshuffled
  queue, not pure re-random-pick, so nobody gets starved of a turn) -- humans
  don't poll the whole room before deciding it's gone quiet either.
- **discussion_silence_threshold`** (default 4, `game_rules.yaml`): discussion
  now ends after N consecutive declines in a row, not only once literally
  everyone has individually passed -- this is the actual cost fix, since the
  expensive case was always the wind-down tail where nobody has anything left
  to add.
- Also shortened the "thought" instruction specifically on poll prompts (a
  brief one-line gut-check instead of "a few sentences of real analysis") --
  deliberately *not* applied to the RULES_BLOCK's general framing or to any
  real decision (votes, night actions, actual speech), since blanket-shrinking
  "thought" everywhere was the exact mistake that hurt play quality in an
  earlier session. This is scoped to the low-stakes "do I want to jump in right
  now" check only.
- `max_tokens` deliberately left untouched at 1400 -- lowering it to save
  money would risk reintroducing the reasoning-token starvation bug just fixed
  for Gemini/GLM.

## Current state

- 36 tests passing, all against the free mock provider (no API cost to run
  the suite).
- Repo: https://github.com/LAKSHYAJAIN16/LLM-mafia
- Games only run when explicitly requested -- this simulator makes real,
  metered API calls.
- Roster notes (`config/models.openrouter.yaml`): `gemini-2.5-pro-or` and
  `glm-4.6-or` are disabled (both confirmed to starve on invisible reasoning
  tokens via real games, see above) -- `gemini-3.6-flash-or` still covers
  Google.
- Per explicit user instruction: commit and push after every change, not just
  when asked.
