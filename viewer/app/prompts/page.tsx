import SiteNav from "../components/SiteNav";
import { PROMPTS } from "@/lib/prompts";

const PHASE_LABEL: Record<string, string> = {
  system: "System",
  day: "Day",
  night: "Night",
  meta: "Meta",
};

export default function PromptsPage() {
  return (
    <div className="wrap">
      <SiteNav />
      <h1>Prompts</h1>
      <p className="subtitle">
        Every prompt template the simulation actually sends to a model, {PROMPTS.length} in total. Values the
        engine fills in at call time -- the transcript, alive players, a specific seat -- are shown as{" "}
        <code>&lt;angle-bracket placeholders&gt;</code>.
      </p>

      {PROMPTS.map((p) => (
        <div key={p.id} className="prompt-card">
          <div className="prompt-meta">
            <span className={`phase-badge phase-${p.phase}`}>{PHASE_LABEL[p.phase]}</span>
            <span>{p.role}</span>
          </div>
          <h2>{p.title}</h2>
          <p className="prompt-purpose">{p.purpose}</p>
          <pre className="prompt-text">{p.text}</pre>
          <p className="prompt-source">{p.source}</p>
        </div>
      ))}

      <p className="placeholder-note">
        This page mirrors mafia_sim/game/prompts.py, mafia_sim/game/summarizer.py, and the regenerate note built in
        mafia_sim/agents/player_agent.py by hand (see viewer/lib/prompts.ts) -- there&apos;s no shared schema
        between the Python engine and this viewer, so it&apos;s only as current as the last time someone updated
        both.
      </p>
    </div>
  );
}
