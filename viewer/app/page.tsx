import Link from "next/link";
import { listGames } from "@/lib/games";

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

export default async function GamesListPage() {
  const games = await listGames();

  return (
    <div className="wrap">
      <h1>MafiaSim Replays</h1>
      <p className="subtitle">{games.length} game(s) found</p>

      {games.length === 0 ? (
        <p className="empty">
          No games found. Run one with <code>python -m mafia_sim run</code>, or set{" "}
          <code>MAFIA_RESULTS_DIR</code> if your results live elsewhere.
        </p>
      ) : (
        games.map((g) => (
          <Link key={g.game_id} href={`/games/${g.game_id}`} className="game-row">
            <div className="id">{g.game_id}</div>
            <div className="row-meta">
              <span className={winnerClass(g.winner)}>{winnerLabel(g.winner)}</span>
              <span>{g.days} day(s)</span>
              <span>{g.player_count} players</span>
              <span className="cost">${g.total_cost_usd.toFixed(4)}</span>
              {g.format_failure_count > 0 && (
                <span className="warn">{g.format_failure_count} format failure(s)</span>
              )}
            </div>
          </Link>
        ))
      )}
    </div>
  );
}
