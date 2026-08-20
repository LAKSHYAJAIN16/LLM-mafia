from __future__ import annotations

import random

from ..game.parsing import parse_json_object, resolve_seat
from ..game.state import GameState
from ..providers.base import ChatProvider
from ..providers.factory import ModelSpec


def _has_value(v) -> bool:
    if isinstance(v, list):
        return any(str(x).strip() for x in v)
    return bool(str(v or "").strip())


class PlayerAgent:
    """Wraps one roster model as a game participant: issues a prompt, parses the
    required JSON fields back out, resolves any player-name fields to exact seats,
    and retries on malformed output before falling back to a random legal action.
    """

    def __init__(self, spec: ModelSpec, provider: ChatProvider, rules: dict):
        self.spec = spec
        self.provider = provider
        self.rules = rules

    def _track_cost(self, state: GameState, resp) -> None:
        cost = resp.cost_usd
        if not cost and (self.spec.price_per_1m_input or self.spec.price_per_1m_output):
            cost = (resp.prompt_tokens / 1_000_000) * (self.spec.price_per_1m_input or 0.0) + (
                resp.completion_tokens / 1_000_000
            ) * (self.spec.price_per_1m_output or 0.0)
        state.add_cost(self.spec.key, cost)

    def ask(
        self,
        state: GameState,
        system_prompt: str,
        user_prompt: str,
        required_keys: list[str],
        target_keys: dict[str, list[str]] | None = None,
        seat: str | None = None,
        purpose: str = "",
    ) -> dict:
        attempts = self.rules.get("max_format_retries", 2) + 1

        for attempt in range(1, attempts + 1):
            resp = self.provider.complete(
                system_prompt,
                user_prompt,
                temperature=self.rules.get("temperature", 0.9),
                max_tokens=self.rules.get("max_tokens", 500),
                timeout=self.rules.get("request_timeout_seconds", 60),
            )
            state.log_raw_call(
                seat=seat,
                model_key=self.spec.key,
                purpose=purpose,
                attempt=attempt,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_text=resp.text,
                error=resp.error,
                cost_usd=resp.cost_usd,
            )
            if resp.error:
                continue
            self._track_cost(state, resp)

            obj = parse_json_object(resp.text)
            if obj is None:
                continue

            missing = [k for k in required_keys if not _has_value(obj.get(k))]
            if missing:
                continue

            resolved = dict(obj)
            valid = True
            if target_keys:
                for key, candidates in target_keys.items():
                    if key in resolved:
                        seat_val = resolve_seat(str(resolved[key]), candidates)
                        if seat_val is None:
                            valid = False
                            break
                        resolved[key] = seat_val
            if not valid:
                continue

            return resolved

        state.note_format_failure(self.spec.key)
        fallback: dict = {"thought": "", "message": "(no response)", "messages": ["(no response)"]}
        if target_keys:
            for key, candidates in target_keys.items():
                if candidates:
                    fallback[key] = random.choice(candidates)
        return fallback
