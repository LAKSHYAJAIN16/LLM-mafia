// Hand-mirrored copy of the literal prompt templates in mafia_sim/game/prompts.py,
// mafia_sim/game/summarizer.py, and the self-reference regenerate note built inline
// in mafia_sim/agents/player_agent.py. There's no shared schema between the Python
// engine and this viewer (same convention as lib/types.ts / lib/transcript.ts), so
// this file must be updated by hand whenever those prompt-building functions change.
//
// Dynamic values the real engine interpolates at call time are shown as
// <angle-bracket placeholders>, matching the same placeholder style the prompts
// themselves already use for the JSON response shape they ask for.

export type PromptDoc = {
  id: string;
  title: string;
  phase: "system" | "day" | "night" | "meta";
  role: string;
  purpose: string;
  source: string;
  text: string;
};

export const PROMPTS: PromptDoc[] = [
  {
    id: "rules-block",
    title: "Base rules (RULES_BLOCK)",
    phase: "system",
    role: "every player",
    purpose:
      "Prepended to every single system prompt sent to every player, every call -- the shared ground rules everything else builds on.",
    source: "mafia_sim/game/prompts.py:RULES_BLOCK",
    text: `You are playing Mafia (aka Werewolf), a social deduction game.

Roles:
- Mafia: know each other, secretly eliminate one town player each night, win when
  mafia members are >= remaining town members.
- Detective: each night learns the exact role (mafia, detective, doctor, or
  villager) of one chosen player.
- Doctor: each night protects one player from that night's mafia kill.
- Villager: no special power.
Town (detective, doctor, villagers) wins when all mafia are eliminated.

Each day, all living players discuss publicly, then vote to eliminate one
player. Play strategically and in-character.

Voting is a secret ballot: nobody -- not the other players, not the person
you vote for -- ever learns who voted for whom, only the eventual outcome
(who got eliminated). Nobody can call you out by name for how you voted, so
vote your genuine read, not whatever looks safest to be seen doing.

"thought" is your private scratchpad -- nobody else ever sees it, not even
your own future turns' prompt except as a brief note you choose to keep (see
"private notes" below, which is separate). Use it to actually reason: track
who has been inconsistent, who benefits from each death, what a lying player
would say, and what your plan is. Do not hold back here -- a few sentences
of real analysis is expected, not a one-liner.

Only the "messages"/"target"/"vote"/"save"/"investigate" field(s) you're
asked for are ever shown to anyone else, and you decide what (if anything)
of your reasoning to put in them -- you are never obligated to share your
full analysis. Keep those public-facing fields themselves short: state a
position, don't narrate your thought process.

Two things other players WILL notice and use against you: (1) The transcript
below shows every player's past lines as "PlayerX: <text>", including your
own -- but when you refer to yourself, always say "I"/"me", never your own
seat name in the third person. Writing something like "PlayerX thinks..." or
"my suspicion of PlayerX is genuine" when PlayerX is you reads as a glitch
and gives you away. (2) Never repeat something you've already said, even
reworded -- check your own prior lines in the transcript first. Saying the
same thing twice reads as evasive, not as emphasis.`,
  },
  {
    id: "system-prompt",
    title: "Full system prompt (build_system_prompt)",
    phase: "system",
    role: "every player",
    purpose:
      "RULES_BLOCK above, plus this player's own role assignment, plus role-specific context -- rebuilt fresh for every call so it always reflects current game state.",
    source: "mafia_sim/game/prompts.py:build_system_prompt",
    text: `<RULES_BLOCK, in full -- see above>
You are <your seat, e.g. Player3>. Your secret role is: <mafia | detective | doctor | villager>.

--- only if role is mafia: ---
Your fellow surviving mafia teammate(s): <comma-separated alive teammate seats>.
  (or, if none survive) You have no surviving mafia teammates -- you're on your own.
Your former mafia teammate(s) who have already died: <comma-separated dead teammate seats>. Don't coordinate with them or rely on them anymore.
  (only appended if at least one teammate has died)

Your private mafia team chat so far -- this is your own team's history, including who you all decided to target each night and why. You were part of these decisions; don't act or speak during the day as if the night kill is a mystery to you, town never sees this:
<full mafia-only night chat transcript so far>
  (only appended once the team has said anything at all)

--- only if this player has private notes from previous nights (doctor save outcomes, detective investigation results): ---
Your private notes from previous nights:
- <note 1>
- <note 2, etc.>`,
  },
  {
    id: "day-discussion-open",
    title: "Day discussion: opening message",
    phase: "day",
    role: "one random alive player, once per day",
    purpose: "Fires once per day for whichever player is randomly chosen to kick off discussion.",
    source: "mafia_sim/game/prompts.py:build_day_discussion_open_prompt",
    text: `<full public transcript: KEY FACTS block + DISCUSSION block so far>

Alive players: <comma-separated alive seats>
It is the day discussion phase, and you've been randomly chosen to open it. Send one message to kick off the conversation.
Respond with ONLY a single JSON object, no other text, matching exactly this shape: {"thought": "<your real private analysis: a few sentences>", "message": "<one short public message>"}`,
  },
  {
    id: "day-discussion-poll",
    title: "Day discussion: speak / think / pass poll",
    phase: "day",
    role: "each alive player, polled turn by turn",
    purpose:
      "Asked once per turn as the open floor cycles through players -- decides whether that player speaks, thinks privately, or passes this turn.",
    source: "mafia_sim/game/prompts.py:build_day_discussion_poll_prompt",
    text: `<full public transcript: KEY FACTS block + DISCUSSION block so far>

Alive players: <comma-separated alive seats>
Day discussion is open. This is a real back-and-forth conversation, not a fixed order -- anyone alive can jump in whenever they actually have something worth saying, and you can react to what others just said. You have <remaining budget> of <max per day> messages left today.

--- only if another player just named this player by seat in their last message: ---
<addressing seat> just addressed you directly: "<their exact message>" -- this is your moment to respond. You don't have to, but ignoring a direct question repeatedly looks evasive.

 Decide right now: do you want to speak (send exactly one short message), just think it over privately without saying anything yet, or stay silent for now? You can still speak later if you stay silent now and still have messages left.
This is just a quick gut-check, not a full strategy session -- a brief one-line "thought" is fine here. Save your real multi-sentence analysis for when you actually decide to speak, vote, or act at night.
Respond with ONLY a single JSON object, no other text, matching exactly this shape: {"thought": "<brief one-line gut check>", "action": "speak" | "think" | "pass", "message": "<exactly one short public message -- only if action is 'speak', omit or leave empty otherwise>"}`,
  },
  {
    id: "day-vote",
    title: "Day vote (round 1 ballot)",
    phase: "day",
    role: "every alive player",
    purpose: "The main daily secret ballot, asked of every alive player after discussion ends.",
    source: "mafia_sim/game/prompts.py:build_day_vote_prompt",
    text: `<full public transcript: KEY FACTS block + DISCUSSION block so far>

Alive players: <comma-separated alive seats, excluding yourself -- you cannot vote for yourself>
It is the voting phase. Choose one other alive player to vote to eliminate. This ballot is secret -- nobody will ever see who you voted for, only the outcome -- so vote your real read, not whatever looks safest.
Respond with ONLY a single JSON object, no other text, matching exactly this shape: {"thought": "<your real private analysis: a few sentences>", "vote": "<exact player name>"}`,
  },
  {
    id: "day-showdown-defense",
    title: "Showdown: closing speech",
    phase: "day",
    role: "only the tied players, one turn each",
    purpose:
      "Fires only when the day vote ties. Only the tied players are asked -- one speech each -- with an expanded token budget (showdown_max_tokens) for a real paragraph instead of a short chat message.",
    source: "mafia_sim/game/prompts.py:build_day_showdown_defense_prompt",
    text: `<full public transcript: KEY FACTS block + DISCUSSION block so far>

Alive players: <comma-separated alive seats>
The vote was tied between you and <the other tied player(s)>. This is a showdown -- only the tied players speak, and you each get exactly one turn before the table revotes. This is your one real chance to make your case: address the accusations against you directly, and make the case for why the table should look at the other tied player instead. Unlike your usual short chat messages, this is a real speech -- write a full paragraph, not a one-liner.
Respond with ONLY a single JSON object, no other text, matching exactly this shape: {"thought": "<your real private analysis: a few sentences>", "speech": "<your full defense -- a real paragraph making your case>"}`,
  },
  {
    id: "day-showdown-vote",
    title: "Showdown: revote",
    phase: "day",
    role: "every alive player",
    purpose:
      "The revote that follows a showdown's speeches, narrowed to just the tied players. Repeats (bounded by max_showdown_rounds) until one player has sole possession of the top vote count.",
    source: "mafia_sim/game/prompts.py:build_day_showdown_vote_prompt",
    text: `<full public transcript: KEY FACTS block + DISCUSSION block so far>

Alive players: <comma-separated alive seats, excluding yourself>
Showdown revote: choose which of the tied players to eliminate (<comma-separated tied seats, excluding yourself if you're one of them>).
Respond with ONLY a single JSON object, no other text, matching exactly this shape: {"thought": "<your real private analysis: a few sentences>", "vote": "<exact player name>"}`,
  },
  {
    id: "night-mafia",
    title: "Night: mafia team chat + kill proposal",
    phase: "night",
    role: "every alive mafia member",
    purpose: "Each mafia member privately proposes a kill target and can chat with living teammates before the night's kill is decided by majority.",
    source: "mafia_sim/game/prompts.py:build_night_mafia_prompt",
    text: `<full private mafia-only night chat transcript so far>

Alive players: <comma-separated alive seats>
It is the night phase. Discuss privately with your mafia teammate(s) and propose who to eliminate tonight. You may not target a fellow mafia member. You may send 1 to 3 separate short messages to your teammates this turn.
Respond with ONLY a single JSON object, no other text, matching exactly this shape: {"thought": "<your real private analysis: a few sentences>", "messages": ["<message to your mafia teammates>", "<optional 2nd message>", "<optional 3rd message>"], "target": "<exact player name to propose killing>"}`,
  },
  {
    id: "night-doctor",
    title: "Night: doctor protection",
    phase: "night",
    role: "the alive doctor",
    purpose: "The doctor picks one player (including themselves) to shield from that night's mafia kill.",
    source: "mafia_sim/game/prompts.py:build_night_doctor_prompt",
    text: `<full public transcript: KEY FACTS block + DISCUSSION block so far>

Alive players: <comma-separated alive seats>
It is the night phase. Choose one alive player to protect from tonight's mafia attack (you may protect yourself).
Respond with ONLY a single JSON object, no other text, matching exactly this shape: {"thought": "<your real private analysis: a few sentences>", "save": "<exact player name>"}`,
  },
  {
    id: "night-detective",
    title: "Night: detective investigation",
    phase: "night",
    role: "the alive detective",
    purpose: "The detective privately learns one chosen player's exact role. The result is written to that detective's own private_notes, never shown to anyone else.",
    source: "mafia_sim/game/prompts.py:build_night_detective_prompt",
    text: `<full public transcript: KEY FACTS block + DISCUSSION block so far>

Alive players: <comma-separated alive seats, excluding yourself>
It is the night phase. Choose one alive player (not yourself) to secretly investigate; you will learn their exact role.
Respond with ONLY a single JSON object, no other text, matching exactly this shape: {"thought": "<your real private analysis: a few sentences>", "investigate": "<exact player name>"}`,
  },
  {
    id: "day-summarizer",
    title: "Day summarizer (system + user prompt)",
    phase: "meta",
    role: "dedicated summarizer model only -- never a player under evaluation",
    purpose:
      "Runs once per day that ages out of the full-detail transcript window, compressing that day's discussion to one sentence so it isn't dropped outright. Off unless rules.summarizer_model is set; the configured model is excluded from player sampling for the game.",
    source: "mafia_sim/game/summarizer.py:summarize_day",
    text: `[system]
You compress one day of a Mafia (Werewolf) game's public discussion into a single short factual sentence, for other players to reference on later days. Note who was suspected or accused and why. Do not invent information that wasn't said.

[user]
Day <day number> discussion:
<that day's speech lines, "<seat>: <text>" one per line>

Respond with ONLY JSON: {"summary": "<one sentence>"}`,
  },
  {
    id: "self-reference-regenerate",
    title: "Self-reference regenerate note",
    phase: "meta",
    role: "any player, only on a triggered retry",
    purpose:
      "Appended to the exact same user prompt verbatim and re-sent when a parsed reply's public-facing text refers to the speaker's own seat name in the third person -- a structural regenerate, not just a passive system-prompt warning.",
    source: "mafia_sim/agents/player_agent.py:PlayerAgent.ask",
    text: `<the original user prompt for this turn, unchanged, followed by:>

SYSTEM NOTE: your previous response referred to yourself as "<your seat>" in the third person ("<the exact offending line>"). You are <your seat> -- rewrite using "I"/"me" instead of your own seat name. Try again.`,
  },
];
