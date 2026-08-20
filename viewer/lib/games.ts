import fs from "fs/promises";
import path from "path";
import type { GameRecord, GameSummary } from "./types";

// The Python simulator writes results/games/<id>.json next to this Next.js
// project (mafia_sim/sim/logger.py:ResultsLogger). Override with
// MAFIA_RESULTS_DIR if games live somewhere else.
function resultsDir(): string {
  return process.env.MAFIA_RESULTS_DIR || path.join(process.cwd(), "..", "results", "games");
}

async function readGameFile(filePath: string): Promise<GameRecord> {
  const raw = await fs.readFile(filePath, "utf-8");
  return JSON.parse(raw) as GameRecord;
}

/** Lists every saved game, newest first (game ids embed a sortable UTC timestamp). */
export async function listGames(): Promise<GameSummary[]> {
  const dir = resultsDir();
  let entries: string[];
  try {
    entries = await fs.readdir(dir);
  } catch {
    return [];
  }

  const files = entries.filter((f) => f.endsWith(".json"));
  const games = await Promise.all(
    files.map(async (file) => {
      const record = await readGameFile(path.join(dir, file));
      const summary: GameSummary = {
        game_id: record.game_id,
        winner: record.winner,
        days: record.days,
        player_count: record.players.length,
        total_cost_usd: record.total_cost_usd ?? 0,
        format_failure_count: Object.values(record.format_failures ?? {}).reduce((a, b) => a + b, 0),
      };
      return summary;
    })
  );

  return games.sort((a, b) => (a.game_id < b.game_id ? 1 : -1));
}

/** Loads one full game record by id, or null if it doesn't exist. */
export async function loadGame(gameId: string): Promise<GameRecord | null> {
  const dir = resultsDir();
  const filePath = path.join(dir, `${gameId}.json`);
  try {
    return await readGameFile(filePath);
  } catch {
    return null;
  }
}
