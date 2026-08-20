from __future__ import annotations

from ..providers.base import ChatProvider, ProviderResponse
from .parsing import parse_json_object

_SYSTEM = (
    "You compress one day of a Mafia (Werewolf) game's public discussion into a "
    "single short factual sentence, for other players to reference on later days. "
    "Note who was suspected or accused and why. Do not invent information that "
    "wasn't said."
)


def summarize_day(
    provider: ChatProvider, day: int, speech_text: str, rules: dict
) -> tuple[str | None, ProviderResponse, str, str]:
    """Compresses one day's discussion into one sentence via a dedicated summarizer
    model (never one of the roster models under evaluation). Returns (None, resp, ...)
    on any failure -- summarization is a token-saving nicety, not required for
    correctness, so callers should fall back to silently dropping the old text as
    before. The raw ProviderResponse and the exact (system, user) prompt text are
    always returned too, so the caller can account for cost and log the raw call
    even when parsing fails.
    """
    user_prompt = (
        f"Day {day} discussion:\n{speech_text}\n\n"
        'Respond with ONLY JSON: {"summary": "<one sentence>"}'
    )
    resp = provider.complete(
        _SYSTEM,
        user_prompt,
        temperature=0.3,
        max_tokens=120,
        timeout=rules.get("request_timeout_seconds", 60),
    )
    if resp.error:
        return None, resp, _SYSTEM, user_prompt

    obj = parse_json_object(resp.text)
    if not obj:
        return None, resp, _SYSTEM, user_prompt
    summary = str(obj.get("summary", "")).strip()
    return (summary or None), resp, _SYSTEM, user_prompt
