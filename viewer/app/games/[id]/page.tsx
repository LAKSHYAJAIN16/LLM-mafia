import Link from "next/link";
import { notFound } from "next/navigation";
import { loadGame } from "@/lib/games";
import { buildTimeline, CAUSE_LABELS } from "@/lib/transcript";
import type { Player } from "@/lib/types";
import Transcript from "./Transcript";

function winnerLabel(winner: string | null): string {
  if (winner === "mafia") return "MAFIA";
  if (winner === "town") return "TOWN";
  return "DRAW / timeout";
}

function winnerClass(winner: string | null): string {
  if (winner === "mafia") return "winner-mafia";
  if (winner === "town") return "winner-town";
  return "winner-draw";
}

function outcome(p: Player): string {
  if (p.alive) return "alive at end";
  const cause = (p.death_cause && CAUSE_LABELS[p.death_cause]) || p.death_cause || "unknown";
  return `died day ${p.death_day} (${cause})`;
}

export default async function GamePage({ params }: PageProps<"/games/[id]">) {
  const { id } = await params;
  const record = await loadGame(id);
  if (!record) notFound();

  const items = buildTimeline(record);

  return (
    <div className="wrap">
      <p className="subtitle">
        <Link href="/">&larr; all games</Link>
      </p>
      <h1>Mafia replay: {record.game_id}</h1>
      <p className="subtitle">
        Winner: <span className={winnerClass(record.winner)}>{winnerLabel(record.winner)}</span> &middot;{" "}
        {record.days} day(s) &middot; Cost: <span className="cost">${record.total_cost_usd.toFixed(4)}</span>
      </p>

      <details className="cast">
        <summary>Reveal cast, roles &amp; outcomes (spoilers)</summary>
        <table>
          <thead>
            <tr>
              <th>Seat</th>
              <th>Model</th>
              <th>Role</th>
              <th>Outcome</th>
            </tr>
          </thead>
          <tbody>
            {record.players.map((p) => (
              <tr key={p.seat}>
                <td>{p.seat}</td>
                <td>{p.model_key}</td>
                <td className={p.role === "mafia" ? "role-mafia" : "role-town"}>{p.role}</td>
                <td>{outcome(p)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>

      <Transcript items={items} />
    </div>
  );
}
