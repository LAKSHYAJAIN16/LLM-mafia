from __future__ import annotations

from html import escape

_CSS = """
:root { color-scheme: dark; }
* { box-sizing: border-box; }
body {
  margin: 0; padding: 2rem 1rem 4rem; background: #14161c; color: #e6e6ea;
  font-family: -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
  line-height: 1.5;
}
.wrap { max-width: 760px; margin: 0 auto; }
h1 { font-size: 1.3rem; margin: 0 0 0.25rem; }
.meta { color: #9a9caa; font-size: 0.9rem; margin-bottom: 1.25rem; }
.winner-mafia { color: #ff6b6b; font-weight: 600; }
.winner-town { color: #6bcB77; font-weight: 600; }
.winner-draw { color: #d9c46b; font-weight: 600; }
details.cast {
  background: #1c1f28; border: 1px solid #2a2e3a; border-radius: 10px;
  padding: 0.75rem 1rem; margin-bottom: 1.5rem;
}
details.cast summary { cursor: pointer; font-weight: 600; }
table { width: 100%; border-collapse: collapse; margin-top: 0.75rem; font-size: 0.9rem; }
th, td { text-align: left; padding: 0.35rem 0.5rem; border-bottom: 1px solid #2a2e3a; }
th { color: #9a9caa; font-weight: 500; }
.role-mafia { color: #ff6b6b; }
.role-town { color: #6bcB77; }
.controls { display: flex; gap: 0.5rem; margin-bottom: 1.5rem; }
button {
  background: #2a2e3a; color: #e6e6ea; border: 1px solid #3a3f4f; border-radius: 8px;
  padding: 0.45rem 0.9rem; font-size: 0.85rem; cursor: pointer;
}
button:hover { background: #343948; }
.heading { color: #9a9caa; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em;
  margin: 1.5rem 0 0.5rem; }
.entry { border-radius: 10px; padding: 0.55rem 0.85rem; margin: 0.35rem 0; font-size: 0.92rem; }
.entry.hidden-step { display: none; }
.entry-system { background: #241d1d; border-left: 3px solid #d9c46b; }
.entry-speech { background: #1c1f28; }
.entry-vote { background: #1c1f28; border-left: 3px solid #6b8fd9; font-size: 0.85rem; color: #b8bacb; }
.entry-mafia_chat { background: #241a1a; border-left: 3px solid #ff6b6b; }
.entry-thought { background: transparent; border-left: 3px solid #4a4e5c; color: #9a9caa;
  font-style: italic; padding-top: 0.35rem; padding-bottom: 0.35rem; }
.entry-summary { background: #1a2024; border-left: 3px solid #6b8fd9; color: #b8bacb; font-size: 0.85rem; }
.speaker { font-weight: 600; margin-right: 0.4rem; }
.tag { font-size: 0.7rem; color: #b8bacb; margin-left: 0.4rem; }
"""


def _winner_class(winner: str | None) -> str:
    return {"mafia": "winner-mafia", "town": "winner-town"}.get(winner or "", "winner-draw")


def _role_class(team: str) -> str:
    return "role-mafia" if team == "mafia" else "role-town"


_CAUSE_LABELS = {"voted_out": "voted out", "killed": "killed at night"}


def _player_row(p: dict) -> str:
    if p["alive"]:
        outcome = "alive at end"
    else:
        cause = _CAUSE_LABELS.get(p["death_cause"], p["death_cause"])
        outcome = f"died day {p['death_day']} ({cause})"
    team = "mafia" if p["role"] == "mafia" else "town"
    return (
        f"<tr><td>{escape(p['seat'])}</td><td>{escape(p['model_key'])}</td>"
        f"<td class='{_role_class(team)}'>{escape(p['role'])}</td><td>{escape(outcome)}</td></tr>"
    )


_KIND_LABELS = {
    "mafia_chat": "mafia-only",
    "thought": "private thought",
    "speech": "speech",
    "vote": "vote",
    "system": "system",
}


def _entry_div(kind: str, speaker: str | None, text: str) -> str:
    speaker_html = f"<span class='speaker'>{escape(speaker)}</span>" if speaker else ""
    tag = f"<span class='tag'>{escape(_KIND_LABELS.get(kind, kind))}</span>"
    return f"<div class='entry entry-{escape(kind)}'>{speaker_html}{escape(text)}{tag}</div>"


def render_game_html(record: dict) -> str:
    game_id = record["game_id"]
    winner = record.get("winner")
    winner_label = {"mafia": "MAFIA", "town": "TOWN"}.get(winner or "", "DRAW / timeout")
    days = record.get("days", 0)
    players = record.get("players", [])
    day_summaries = record.get("day_summaries", {})

    rows = "\n".join(_player_row(p) for p in players)

    # All logs (public speech/system, mafia-only chat, private thoughts, and secret
    # ballots) share one global "seq" counter, so merging and sorting by it
    # reproduces the true turn-by-turn order the game actually happened in -- e.g. a
    # player's private "thought" appears right before the public message it led to,
    # not lumped separately. Votes come from vote_log (spectator-only) rather than
    # public_log, since ballots are secret from the players themselves.
    all_entries = [
        *record.get("public_log", []),
        *record.get("mafia_log", []),
        *record.get("thought_log", []),
        *record.get("vote_log", []),
    ]
    all_entries.sort(key=lambda e: e.get("seq", 0))

    entries_html: list[str] = []
    last_section: tuple[int, str] | None = None
    summarized_days: set[int] = set()
    for e in all_entries:
        section = (e["day"], e["phase"])
        if section != last_section:
            if last_section is not None and last_section[0] not in summarized_days:
                summary = day_summaries.get(last_section[0]) or day_summaries.get(str(last_section[0]))
                if summary:
                    entries_html.append(
                        f"<div class='entry entry-summary'>Day {last_section[0]} digest (used to compress "
                        f"this day once it aged out of the model's prompt): {escape(summary)}</div>"
                    )
                summarized_days.add(last_section[0])
            label = "Night" if e["phase"] == "night" else "Day"
            entries_html.append(f"<div class='heading'>{label} {e['day']}</div>")
            last_section = section
        entries_html.append(_entry_div(e["kind"], e.get("speaker"), e["text"]))

    if last_section is not None and last_section[0] not in summarized_days:
        summary = day_summaries.get(last_section[0]) or day_summaries.get(str(last_section[0]))
        if summary:
            entries_html.append(
                f"<div class='entry entry-summary'>Day {last_section[0]} digest (used to compress this "
                f"day once it aged out of the model's prompt): {escape(summary)}</div>"
            )

    transcript = "\n".join(entries_html)

    return f"""<meta charset="utf-8">
<title>Mafia replay -- {escape(game_id)}</title>
<style>{_CSS}</style>
<div class="wrap">
  <h1>Mafia replay: {escape(game_id)}</h1>
  <div class="meta">
    Winner: <span class="{_winner_class(winner)}">{winner_label}</span> &middot; {days} day(s)
  </div>

  <details class="cast">
    <summary>Reveal cast, roles &amp; outcomes (spoilers)</summary>
    <table>
      <tr><th>Seat</th><th>Model</th><th>Role</th><th>Outcome</th></tr>
      {rows}
    </table>
  </details>

  <div class="controls">
    <button onclick="stepMode(true)">Step through</button>
    <button onclick="stepMode(false)">Show full transcript</button>
    <button id="playBtn" onclick="togglePlay()">Play</button>
    <button onclick="stepOnce()">Next</button>
  </div>

  <div id="transcript">
    {transcript}
  </div>
</div>
<script>
const entries = Array.from(document.querySelectorAll('.entry'));
let revealed = entries.length;
let playing = null;

function render() {{
  entries.forEach((el, i) => el.classList.toggle('hidden-step', i >= revealed));
}}
function stepMode(on) {{
  revealed = on ? 0 : entries.length;
  render();
}}
function stepOnce() {{
  if (revealed < entries.length) revealed++;
  render();
}}
function togglePlay() {{
  const btn = document.getElementById('playBtn');
  if (playing) {{
    clearInterval(playing); playing = null; btn.textContent = 'Play';
    return;
  }}
  if (revealed >= entries.length) revealed = 0;
  btn.textContent = 'Pause';
  playing = setInterval(() => {{
    if (revealed >= entries.length) {{ clearInterval(playing); playing = null; btn.textContent = 'Play'; return; }}
    revealed++; render();
  }}, 1100);
}}
render();
</script>
"""
