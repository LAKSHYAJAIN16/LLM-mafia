// A hand-maintained changelog of what's shipped on MafiaSim, newest first. There's no
// database or CMS behind this -- each entry is written by hand alongside the commit(s)
// it describes (see the git hashes on each post) whenever a real, user-visible or
// architecturally meaningful change ships. Not every commit gets its own post; closely
// related commits from the same piece of work are grouped into one.
//
// To add an entry: prepend a new object to POSTS below with the next post's data,
// dated the day it shipped, referencing the real commit hash(es) from `git log`.

export type BlogPost = {
  slug: string;
  date: string; // YYYY-MM-DD, the day the work actually shipped
  title: string;
  summary: string;
  commits: { hash: string; message: string }[];
  body: string[]; // paragraphs
};

export const POSTS: BlogPost[] = [
  {
    slug: "dynamic-speaking-rate-nudge",
    date: "2026-08-20",
    title: "An opt-in nudge based on a real research paper, off by default",
    summary: "\"Time to Talk\" (Eckhaus et al. 2025) proposed biasing an agent's speak/stay-quiet decision by its share of recent messages -- added as a toggle, not a default.",
    commits: [{ hash: "dcca4a8", message: "Add an opt-in dynamic speaking-rate nudge (off by default)" }],
    body: [
      "Read through \"Time to Talk: LLM Agents for Asynchronous Group Communication in Mafia Games\" (Eckhaus, Berger, Stanovsky -- EMNLP Findings 2025), which studies an LLM agent playing Mafia asynchronously alongside real humans. Most of its contributions don't transfer directly -- it's built around a live human audience (simulated typing delays, a human-vs-agent detection survey) that doesn't exist in an LLM-vs-LLM simulator -- but one idea is directly portable: its scheduler prompt is dynamically biased based on the agent's own talk rate relative to a fair 1/n share, nudging a quiet agent to speak up and a talkative one to listen more.",
      "Added as GameEngine._speaking_rate_nudge(), which compares a player's share of today's messages so far against 1/n (n = players still in the discussion) and, if noticeably under or over, adds one sentence to that player's next poll prompt. Explicitly gated behind rules[\"dynamic_speaking_rate_nudge\"], defaulting to false -- so games play exactly as before unless it's turned on, per direct request rather than folding it into default behavior.",
    ],
  },
  {
    slug: "removed-cost-share-cap",
    date: "2026-08-20",
    title: "Removed the per-model cost-share cap",
    summary: "max_cost_share_per_model kept ending games early whenever a model happened to get seated twice -- not the failure mode it was meant to catch.",
    commits: [{ hash: "8b2d211", message: "Remove the max_cost_share_per_model guardrail" }],
    body: [
      "max_cost_share_per_model (added earlier today, see \"Retrying OpenRouter's routing hiccups...\" below) was meant to catch one model being disproportionately expensive per token. In practice, with only ~10-11 distinct playable models in the OpenRouter roster and games running 10-12 players, the sampler often has to seat the same model twice -- which alone roughly doubles that model's share of spend and can trip the cap well before it's actually behaving badly. A real 10-player game ended after just one day because a model seated in two seats hit 65% against a 50% cap.",
      "Removed outright: the max_cost_share_per_model rule, the _budget_exceeded_reason() branch that checked it, and the MIN_COST_FOR_SHARE_CHECK constant. The flat max_cost_usd hard cap remains as the only spend backstop.",
    ],
  },
  {
    slug: "prompts-and-blog-pages",
    date: "2026-08-20",
    title: "Added /prompts and /blog to the viewer",
    summary: "A page documenting every literal prompt template the simulation sends, and this changelog.",
    commits: [{ hash: "93ae767", message: "Add /prompts and /blog pages to the viewer; revert vote-oriented discussion framing" }],
    body: [
      "/prompts is a hand-mirrored reference of every prompt template in mafia_sim/game/prompts.py and summarizer.py -- the same manual-sync convention the viewer already uses for game JSON (lib/types.ts, lib/transcript.ts), just applied to prompts instead of game state. /blog is this page.",
      "The same commit also reverted the \"vote-oriented discussion\" framing from earlier today (see \"Telling models the vote was secret the whole time\" below) after it didn't feel right once actually running -- kept the unrelated secret-ballot-awareness half of that change.",
    ],
  },
  {
    slug: "config-driven-daily-message-cap",
    date: "2026-08-20",
    title: "The daily message cap is a config value now, not a constant",
    summary: "Per-player daily message budget moved out of a hardcoded engine.py constant into game_rules.yaml, so it can be tuned per run.",
    commits: [{ hash: "287ae24", message: "Make the daily per-player message cap config-driven, default to 4" }],
    body: [
      "The per-player daily message budget for day discussion used to be a hardcoded constant (MAX_MESSAGES_PER_DAY = 5) in engine.py. Wanted a tighter budget for a specific run without editing code, so it's now rules.get(\"max_messages_per_day\", 5) -- config-driven with the same default, overridable in game_rules.yaml or a per-run rules file.",
      "Defaulted to 4 for now, down from 5.",
    ],
  },
  {
    slug: "self-reference-regenerate",
    date: "2026-08-20",
    title: "Models that talk about themselves in the third person now get a real do-over",
    summary: "A structural regenerate step in PlayerAgent.ask() replaces hoping the system prompt's warning alone sticks.",
    commits: [{ hash: "70c256f", message: "Structurally regenerate messages that self-reference in third person" }],
    body: [
      "Prompt guardrails (RULES_BLOCK) had already been warning models against writing things like \"PlayerX thinks...\" about themselves, but that alone wasn't reliably working -- models kept doing it anyway.",
      "ask() now checks every parsed reply's public-facing fields for the speaker's own seat name, and -- if a retry is available -- re-asks once with the exact offending line quoted back and an explicit correction request, instead of a blind retry. If it's still not fixed on the last attempt, the reply is accepted as-is rather than looping forever.",
    ],
  },
  {
    slug: "explicit-secret-voting",
    date: "2026-08-20",
    title: "Telling models the vote was secret the whole time",
    summary: "Ballots were always structurally secret -- nobody ever actually told the models that.",
    commits: [{ hash: "1e86aca", message: "Make secret voting and vote-oriented discussion explicit in prompts" }],
    body: [
      "The day's ballot has been secret from day one (see \"Secret ballots, tie-vote showdowns, and a raw model I/O log\" below) -- nobody learns who voted for whom, only the outcome -- but that fact was never actually stated to the models themselves. Now it's explicit in RULES_BLOCK, and reinforced again right in the vote prompt itself, at the exact moment it matters.",
      "This commit also tried nudging day discussion itself to explicitly frame every turn around \"who do we vote for\" -- that part didn't feel right once it was actually running (it started to crowd out organic conversation) and was reverted shortly after.",
    ],
  },
  {
    slug: "key-facts-and-cost-saving-summarization",
    date: "2026-08-20",
    title: "Surfacing the facts that matter, and turning on cost-saving summarization",
    summary: "public_transcript_text() now leads with a KEY FACTS block, and the opt-in day-summarizer is on by default.",
    commits: [
      { hash: "bf04c48", message: "Prioritize key facts in the transcript and turn on cost-saving summarization" },
    ],
    body: [
      "Every player prompt resends the full public transcript, and in a long game with a lot of players that's a lot of chatter for a model to weigh a handful of decision-relevant facts against. public_transcript_text() now pulls deaths, eliminations, and other system events into their own leading \"KEY FACTS\" block, separate from the noisier \"DISCUSSION\" block -- same information, same token cost, just reorganized so it's not diluted.",
      "Also turned the day-summarizer on by default (a cheap dedicated model, gpt-5.4-mini-or, compressing a day's discussion to one sentence once it ages out of the full-detail window) -- it existed before but was opt-in and off. Along the way, fixed a real gap: the summarizer model is now actually excluded from player sampling, not just documented as excluded.",
    ],
  },
  {
    slug: "showdown-one-speech-redesign",
    date: "2026-08-20",
    title: "Showdown defenses are one real speech now, not a chat burst",
    summary: "Only the tied players speak in a showdown, each gets exactly one turn, and it's a full paragraph with extra token headroom.",
    commits: [{ hash: "961e8d3", message: "Redesign showdown as a one-speech defense for only the accused players" }],
    body: [
      "Previously a showdown defense polled every alive player using the same short chat-burst mechanic as normal day discussion. Now only the tied players get to speak, exactly once each, and it reads like a real closing statement -- a full paragraph, not a one-liner -- backed by a dedicated showdown_max_tokens budget (2200, vs the base 1400) so there's room to actually write one.",
    ],
  },
  {
    slug: "cost-cap-raised-and-roster-trimmed",
    date: "2026-08-20",
    title: "Raised the cost cap to $2, dropped two expensive/unreliable models",
    summary: "max_cost_usd 1.00 -> 2.00, and Claude Sonnet 5 / Llama 3.3 70B disabled in the OpenRouter roster.",
    commits: [
      { hash: "ac37202", message: "Raise the per-game cost cap from $1 to $2" },
      { hash: "b3ff188", message: "Disable Claude Sonnet 5 and Llama 3.3 70B in the OpenRouter roster" },
    ],
    body: [
      "The per-game hard spending cap moved from $1.00 to $2.00 -- confirmed to be a pure config value (game_rules.yaml), not something hardcoded.",
      "Also disabled two more roster entries: Claude Sonnet 5 (alone accounted for ~50% of one real game's total spend -- genuinely priced too high for cost-sensitive runs, not a bug) and Llama 3.3 70B (repeatedly caught sending near-duplicate messages across turns, a play-quality problem, not a cost one). Gemini 2.5 Pro and GLM-4.6 were already disabled from an earlier reasoning-token-starvation investigation.",
    ],
  },
  {
    slug: "openrouter-retry-and-fairness-guardrails",
    date: "2026-08-20",
    title: "Retrying OpenRouter's routing hiccups, and two new fairness/cost guardrails",
    summary: "A full raw-log review turned up four issues; three got fixed.",
    commits: [
      { hash: "384d772", message: "Retry OpenRouter's transient provider-routing 400s instead of failing immediately" },
      { hash: "04b33c5", message: "Guarantee every player gets heard daily, and cap one model's cost share" },
    ],
    body: [
      "A requested review of a real game's raw call logs surfaced four possible issues. Three got fixed (the fourth -- nudging the detective to claim publicly -- was deliberately skipped, since the ask was for gameplay to evolve naturally rather than being pushed toward a specific strategy).",
      "OpenRouter occasionally returns an HTTP 400 (\"does not support endpoint: completions\") from its multi-backend routing -- confirmed transient, since retrying the identical request succeeds -- so it's now retried the same way a 5xx would be, scoped to OpenRouter only.",
      "Discussion fairness: the open floor could let a day go quiet before every player had even one turn. Fixed by tracking who's been polled and forcing an unseen player to speak before silence is allowed to end the day. This commit also added a max_cost_share_per_model guardrail (0.5) ending a game early if any single model's spend dominated -- it was removed again shortly after (see below), once a real 10-player game showed it triggering too eagerly whenever a model happened to get seated twice.",
    ],
  },
  {
    slug: "reveal-ordering",
    date: "2026-08-20",
    title: "Doctor and detective outcomes now show up right where they happened",
    summary: "Reveal messages were logged after all of a night's actions resolved; now they're inline, right after each player's own turn.",
    commits: [{ hash: "047a9e0", message: "Order doctor/detective outcome reveals right after each player's own action" }],
    body: [
      "Spectator-only \"outcome\" messages -- e.g. \"you protected Player4 -- they were attacked and you saved them!\" -- were being appended after every night action had resolved, so they showed up batched together in the replay instead of right after that player's own turn. Moved the doctor's reveal logic inline, right after the save is read, so console and replay ordering now match true turn order.",
    ],
  },
  {
    slug: "home-casino-page",
    date: "2026-08-20",
    title: "A neon casino-style landing page at /home",
    summary: "Built via the impeccable design workflow, iterated live through several rounds of feedback.",
    commits: [
      { hash: "812e227", message: "Suppress hydration warning from browser extensions on <html>" },
      { hash: "171387b", message: "Add a neon casino /home showcase page, and PRODUCT.md" },
    ],
    body: [
      "A first landing page for the project: a hero with a scrolling marquee ticker, the MAFIASIM wordmark, and a \"Start a Game\" CTA (still just linking to the games list -- deliberately not wired to a real, cost-incurring launch flow yet). Iterated through several rounds live: renamed then reverted back to MAFIASIM, dropped an inaccurate \"real money on the table\" line, removed a House Rules/Ledger section that didn't earn its place, and rebuilt the header ticker as an actual marquee rather than a static kicker label.",
      "Also fixed an unrelated React hydration warning: a browser extension injects a data-phia-extension-fonts-loaded attribute onto <html> before hydration, which is exactly the class of mismatch suppressHydrationWarning exists for.",
    ],
  },
  {
    slug: "mafia-amnesia-self-reference-repetition",
    date: "2026-08-20",
    title: "Three real bugs found from a 15-player game",
    summary: "A mafia player didn't remember its own team's kill decision, plus third-person self-reference and message repetition.",
    commits: [
      { hash: "7946842", message: "Add an explicit 15-player role setup" },
      { hash: "68fb179", message: "Cap the 15-player role setup at 3 mafia, not 4" },
      { hash: "09b05b5", message: "Fix mafia amnesia, third-person self-reference, and message repetition" },
    ],
    body: [
      "A screenshot from the biggest game run so far (15 players) caught a mafia player publicly speculating about \"the mafia\" as if it were a separate outsider deciding kills -- when its own team's chat had made that exact decision. Root cause: mafia players never got their own team's night-chat history carried into later system prompts. build_system_prompt now injects the full mafia chat history for mafia players once it's nonempty, with an explicit \"you were part of these decisions\" framing.",
      "Two more real issues found in the same pass, both mitigated (not fully eliminated, since it's model behavior) via RULES_BLOCK warnings: players occasionally referring to themselves in the third person by seat name, and near-duplicate repeated lines across turns (worst on Llama 3.3 70B).",
    ],
  },
  {
    slug: "next-viewer-and-first-fairness-fixes",
    date: "2026-08-20",
    title: "A Next.js viewer, spectator reveals, and blocked self-votes",
    summary: "A second, more capable replay viewer, plus doctor/detective outcome notes and a same-name-you-just-addressed queue jump.",
    commits: [
      { hash: "e6588c5", message: "Add a hard $1 per-game spending cap" },
      { hash: "896ee8f", message: "Show total game cost on the HTML replay viewer" },
      { hash: "72ab668", message: "Add a Next.js viewer app, reading game JSON directly" },
      { hash: "239d676", message: "Add spectator reveals, block self-votes, and let addressed players jump the queue" },
      { hash: "f2145a0", message: "Support the new reveal log kind in the Next.js viewer" },
      { hash: "447d3c2", message: "Make being addressed by name explicit in the prompt, not just queue order" },
    ],
    body: [
      "Added the first hard per-game spending cap ($1, checked at multiple points so one expensive day can't blow past it before the next check) and surfaced total game cost on the HTML replay, which had been computed but never shown.",
      "Started a second, Next.js-based viewer (this app) reading game JSON directly off disk -- kept alongside the original static HTML generator rather than replacing it, since the plan is a more complex UI than server-rendered Python string templates can comfortably grow into.",
      "Gameplay fixes from the same stretch: the doctor and detective now get a private note about whether their action actually mattered (previously only the detective did); self-votes are blocked outright, since \"vote for yourself if you have no better option\" was mostly being used as an easy out under pressure; and a player who gets addressed by name now explicitly jumps the discussion queue, with the prompt telling them directly they were just asked something.",
    ],
  },
  {
    slug: "open-floor-discussion-and-mafia-teammate-fix",
    date: "2026-08-20",
    title: "Real bugs from real play: mafia not knowing a teammate died, and an open-floor discussion rewrite",
    summary: "Also root-caused why Gemini 2.5 Pro \"never responded\" -- extended-thinking tokens were eating the whole budget.",
    commits: [{ hash: "93ee693", message: "Fix real-game bugs from live play, then rework day discussion into an open floor" }],
    body: [
      "Investigated a report that Gemini 2.5 Pro \"never responds\": every one of its raw responses was 44-82 characters against 300-2200 for every other model in the same game. Its extended-thinking tokens count against max_tokens on OpenRouter's unified endpoint, leaving almost nothing for visible output -- fixed by raising max_tokens game-wide (500 -> 1400) and disabling the model for that game.",
      "Real bug: build_system_prompt listed mafia teammates by role membership with no alive filter, so a lone surviving mafia player kept being told \"your teammate is PlayerX\" long after PlayerX was voted out. Fixed to split alive vs. dead teammates explicitly. Also gave the doctor save-outcome feedback (the detective already had it), and rewrote the fixed round-robin day discussion into an open floor -- one random opener, then each player polled on whether to speak, think, or pass, ending once the room's actually gone quiet instead of not making it feel like a genuine conversation.",
    ],
  },
  {
    slug: "secret-ballots-showdowns-raw-log",
    date: "2026-08-20",
    title: "Secret ballots, tie-vote showdowns, and a raw model I/O log",
    summary: "Votes moved to a spectator-only log, ties now trigger a public defense and revote, and every LLM call gets recorded verbatim.",
    commits: [{ hash: "80297b5", message: "Add secret ballots, tie-vote showdowns, lazy summarization, and raw I/O logging" }],
    body: [
      "Votes used to be written straight into the public log, so every voter after the first could read exactly who everyone before them had voted for -- and it stayed visible in every later prompt too. Moved votes to their own spectator-only vote_log, mirroring how private \"thought\" already worked, so the transcript that actually builds a player's prompt never contains a vote.",
      "A tied day-vote used to resolve via an immediate coin-flip. Now it triggers a showdown: the tied players get a public defense turn, then everyone revotes among just the tied set, repeating (bounded) until it's decisive.",
      "Also added games/<id>.raw.jsonl -- one line per LLM call, every retry included, recording the exact system/user prompt and verbatim response text, for real forensic debugging instead of guessing from the curated replay.",
    ],
  },
  {
    slug: "first-real-game",
    date: "2026-08-19",
    title: "The first real game: 8 players, 8 different companies",
    summary: "DeepSeek, Mistral, GPT-5.5, Gemini, Kimi K2, Llama, Cohere, and Claude Sonnet 5 -- town won, zero mislynches.",
    commits: [{ hash: "708aa05", message: "Add conversation summary documenting the build process and first real game" }],
    body: [
      "The simulator's first real, metered game: DeepSeek Chat and GPT-5.5 as mafia, Kimi K2 as detective, Llama 3.3 70B as doctor. The detective correctly identified the mafia player night one; town voted out DeepSeek Chat day one; the surviving mafia killed the doctor night two; the detective publicly claimed and named both mafia players, and town believed it. Town wins, zero mislynches, total cost $0.2733.",
    ],
  },
  {
    slug: "launch",
    date: "2026-08-19",
    title: "Building MafiaSim: provider adapters, a game engine, and a leaderboard",
    summary: "A simulator where different LLMs play Mafia against each other, so it's possible to see empirically who's actually good at deception and deduction.",
    commits: [
      { hash: "f590288", message: "Initial LLM Mafia simulator: game engine, provider adapters, tournament runner, leaderboard" },
      { hash: "053b5e4", message: "Add vendor-diverse game sampling and a couple open-weight models" },
      { hash: "125502f", message: "Fix stale Gemini and Groq model ids after live verification" },
      { hash: "24ccae7", message: "Add live game-progress streaming, HTML replay viewer, and cost controls" },
      { hash: "8b5f0d7", message: "Fix UTF-8 corruption bug, deepen bot reasoning, add cost tracking, and record private thoughts" },
    ],
    body: [
      "The initial build: raw HTTP provider adapters for every vendor (no SDKs), a classic Mafia game engine (night phase, day discussion, a vote, one stateless completion call per turn), vendor-diverse seating so a game never pits two models from the same company against each other, and a leaderboard tracking win rate, Elo, detection rate, and cost.",
      "Every model ID in the first proposed roster was live-verified against each provider's real API -- several guessed IDs turned out stale. A real UTF-8 corruption bug also turned up in the first live game: em dashes and curly quotes were turning into literal replacement characters, traced to requests' automatic encoding detection guessing wrong, fixed by decoding response bytes as UTF-8 explicitly everywhere.",
      "The single biggest quality lever from this stretch: the private \"thought\" field was initially capped at one short sentence for cost control, which visibly hurt play quality. Rewriting it as an explicit, unrestricted private scratchpad -- while keeping the public-facing field short -- was the fix.",
    ],
  },
];
