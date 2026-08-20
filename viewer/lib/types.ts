export type Role = "mafia" | "detective" | "doctor" | "villager";
export type Winner = "mafia" | "town" | null;
export type DeathCause = "voted_out" | "killed" | null;
export type LogKind = "system" | "speech" | "vote" | "mafia_chat" | "thought";
export type Phase = "day" | "night";

export interface Player {
  seat: string;
  model_key: string;
  role: Role;
  alive: boolean;
  death_day: number | null;
  death_cause: DeathCause;
  private_notes: string[];
}

export interface LogEntry {
  day: number;
  phase: Phase;
  kind: LogKind;
  speaker: string | null;
  text: string;
  seq: number;
}

export interface DayVoteRound {
  day: number;
  round: number;
  votes: Record<string, string>;
}

export interface GameRecord {
  game_id: string;
  winner: Winner;
  days: number;
  players: Player[];
  public_log: LogEntry[];
  mafia_log: LogEntry[];
  thought_log: LogEntry[];
  vote_log: LogEntry[];
  day_votes: DayVoteRound[];
  day_summaries: Record<string, string>;
  format_failures: Record<string, number>;
  cost_usd: Record<string, number>;
  total_cost_usd: number;
}

export interface GameSummary {
  game_id: string;
  winner: Winner;
  days: number;
  player_count: number;
  total_cost_usd: number;
  format_failure_count: number;
}
