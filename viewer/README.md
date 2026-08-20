# MafiaSim Viewer

A Next.js app that reads game records straight from `../results/games/*.json`
(the same files `mafia_sim/sim/logger.py` writes) and renders them, instead
of the static per-game HTML the Python side also generates. This is the place
for richer, interactive UI work -- the static HTML generator still exists and
still runs for every game (quick to open, no server needed), this is the
companion app for anything more involved.

## Running it

```bash
npm install   # first time only
npm run dev
```

Then open the printed URL (usually http://localhost:3000, but Next.js will
pick another port if that one's busy). The games list is read live from disk,
so a game finishing in another terminal just shows up on refresh.

By default it looks for games at `../results/games` (i.e. `results/games` at
the repo root, relative to this directory). Point it elsewhere with:

```bash
MAFIA_RESULTS_DIR=/path/to/results/games npm run dev
```

## Layout

- `lib/types.ts` -- TypeScript types mirroring the JSON shape
  `ResultsLogger.save_game` writes (`mafia_sim/sim/logger.py`). Keep these two
  in sync if the Python side's record shape changes.
- `lib/games.ts` -- server-only file reads: `listGames()` for the index page,
  `loadGame(id)` for one game.
- `lib/transcript.ts` -- merges `public_log`/`mafia_log`/`thought_log`/`vote_log`
  by their shared `seq` counter into one chronological timeline, the same way
  `mafia_sim/sim/html_report.py:render_game_html` does for the static HTML.
  Keep the two in sync.
- `app/page.tsx` -- games list.
- `app/games/[id]/page.tsx` -- one game's cast/roles table + transcript
  (server component, reads the file directly).
- `app/games/[id]/Transcript.tsx` -- the interactive step-through/play
  controls (client component, since it needs browser state).
