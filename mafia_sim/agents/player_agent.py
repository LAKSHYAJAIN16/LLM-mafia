from __future__ import annotations

import random

from ..game.parsing import parse_json_object, resolve_seat
from ..game.state import GameState
from ..providers.base import ChatProvider
from ..providers.factory import ModelSpec


class PlayerAgent:
    """Wraps one roster model as a game participant: issues a prompt, parses the
    required JSON fields back out, resolves any player-name fields to exact seats,
    and retries on malformed output before falling back to a random legal action.
    """

    def __init__(self, spec: ModelSpec, provider: ChatProvider, rules: dict):
        self.spec = spec
        self.provider = provider
        self.rules = rules

    def ask(
        self,
        state: GameState,
        system_prompt: str,
        user_prompt: str,
        required_keys: list[str],
        target_keys: dict[str, list[str]] | None = None,
    ) -> dict:
        attempts = self.rules.get("max_format_retries", 2) + 1

        for _ in range(attempts):
            resp = self.provider.complete(
                system_prompt,
                user_prompt,
                temperature=self.rules.get("temperature", 0.9),
                max_tokens=self.rules.get("max_tokens", 500),
                timeout=self.rules.get("request_timeout_seconds", 60),
            )
            if resp.error:
                continue

            obj = parse_json_object(resp.text)
            if obj is None:
                continue

            missing = [k for k in required_keys if not str(obj.get(k, "")).strip()]
            if missing:
                continue

            resolved = dict(obj)
            valid = True
            if target_keys:
                for key, candidates in target_keys.items():
                    if key in resolved:
                        seat = resolve_seat(str(resolved[key]), candidates)
                        if seat is None:
                            valid = False
                            break
                        resolved[key] = seat
            if not valid:
                continue

            return resolved

        state.note_format_failure(self.spec.key)
        fallback: dict = {"thought": "", "message": "(no response)"}
        if target_keys:
            for key, candidates in target_keys.items():
                if candidates:
                    fallback[key] = random.choice(candidates)
        return fallback
