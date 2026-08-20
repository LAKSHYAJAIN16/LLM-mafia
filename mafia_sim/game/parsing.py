from __future__ import annotations

import json
import re

_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


def parse_json_object(text: str) -> dict | None:
    """Extracts the first {...} block from text and parses it as JSON.
    Models sometimes wrap JSON in markdown fences or add commentary; this
    tolerates that by grabbing the outermost brace span.
    """
    if not text:
        return None
    match = _JSON_BLOCK_RE.search(text)
    if not match:
        return None
    candidate = match.group(0)
    try:
        obj = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def resolve_seat(name: str, candidates: list[str]) -> str | None:
    """Maps a model's free-text player reference onto an exact seat name,
    e.g. 'player 3', 'Player3.', 'PLAYER_3' all resolve to 'Player3'.
    """
    if not name:
        return None
    name = name.strip()

    if name in candidates:
        return name

    normalized = re.sub(r"[^a-z0-9]", "", name.lower())
    for c in candidates:
        if re.sub(r"[^a-z0-9]", "", c.lower()) == normalized:
            return c
    return None
