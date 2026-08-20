from __future__ import annotations

from ..providers.base import ChatProvider, ProviderResponse
from .parsing import parse_json_object

_SYSTEM = (
    "You compress one day of a Mafia (Werewolf) game's public discussion into a "
    "single short factual sentence, for other players to reference on later days. "
    "Note who was suspected or accused and why. Do not invent information that "
    "wasn't said."
)


def summarize_day(provider: ChatProvider, day: int, speech_text: str, rules: dict) -> tuple[str | None, ProviderResponse]:
    """Compresses one day's discussion into one sentence via a dedicated summarizer
    model (never one of the roster models under evaluation). Returns (None, resp) on
    any failure -- summarization is a token-saving nicety, not required for
    correctness, so callers should fall back to silently dropping the old text as
    before. The raw ProviderResponse is always returned too so the caller can still
    account for its cost even when parsing fails.
    """
    resp = provider.complete(
        _SYSTEM,
        f"Day {day} discussion:\n{speech_text}\n\n"
        'Respond with ONLY JSON: {"summary": "<one sentence>"}',
        temperature=0.3,
        max_tokens=120,
        timeout=rules.get("request_timeout_seconds", 60),
    )
    if resp.error:
        return None, resp

    obj = parse_json_object(resp.text)
    if not obj:
        return None, resp
    summary = str(obj.get("summary", "")).strip()
    return (summary or None), resp
