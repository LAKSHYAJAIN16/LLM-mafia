import type { GameRecord, LogEntry } from "./types";

export type TimelineItem =
  | { type: "heading"; key: string; label: string }
  | { type: "summary"; key: string; text: string }
  | { type: "entry"; key: string; entry: LogEntry };

/**
 * Merges public/mafia/thought/vote logs by their shared global seq counter, so
 * replay order matches the game's true turn-by-turn order (e.g. a player's
 * private thought lands right before the public message it led to). Mirrors
 * mafia_sim/sim/html_report.py:render_game_html -- keep the two in sync.
 */
export function buildTimeline(record: GameRecord): TimelineItem[] {
  const allEntries: LogEntry[] = [
    ...record.public_log,
    ...record.mafia_log,
    ...record.thought_log,
    ...record.vote_log,
  ].sort((a, b) => a.seq - b.seq);

  const items: TimelineItem[] = [];
  let lastSection: string | null = null;
  const summarizedDays = new Set<number>();

  const pushSummaryIfAny = (day: number) => {
    if (summarizedDays.has(day)) return;
    const summary = record.day_summaries?.[day] ?? record.day_summaries?.[String(day)];
    summarizedDays.add(day);
    if (summary) {
      items.push({
        type: "summary",
        key: `summary-${day}`,
        text: `Day ${day} digest (used to compress this day once it aged out of the model's prompt): ${summary}`,
      });
    }
  };

  for (const entry of allEntries) {
    const section = `${entry.day}:${entry.phase}`;
    if (section !== lastSection) {
      if (lastSection !== null) {
        const [prevDay] = lastSection.split(":");
        pushSummaryIfAny(Number(prevDay));
      }
      const label = entry.phase === "night" ? "Night" : "Day";
      items.push({ type: "heading", key: `heading-${section}-${entry.seq}`, label: `${label} ${entry.day}` });
      lastSection = section;
    }
    items.push({ type: "entry", key: `entry-${entry.seq}`, entry });
  }

  if (lastSection !== null) {
    const [lastDay] = lastSection.split(":");
    pushSummaryIfAny(Number(lastDay));
  }

  return items;
}

export const KIND_LABELS: Record<string, string> = {
  mafia_chat: "mafia-only",
  thought: "private thought",
  speech: "speech",
  vote: "vote",
  system: "system",
};

export const CAUSE_LABELS: Record<string, string> = {
  voted_out: "voted out",
  killed: "killed at night",
};
