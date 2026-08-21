from __future__ import annotations

import random
import re

from ..game.parsing import parse_json_object, resolve_seat
from ..game.state import GameState
from ..providers.base import ChatProvider
from ..providers.factory import ModelSpec

_FREE_TEXT_KEYS = ("message", "speech")


def _has_value(v) -> bool:
    if isinstance(v, list):
        return any(str(x).strip() for x in v)
    return bool(str(v or "").strip())


def _self_reference_violation(resolved: dict, seat: str | None) -> str | None:
    """Returns the offending line if any public-facing free-text field refers to the
    speaker's own seat name in the third person (e.g. "Player3 thinks..." written by
    Player3 itself) -- a real, structural check rather than hoping the system prompt's
    warning alone sticks, since that alone wasn't reliably preventing it.
    """
    if not seat:
        return None
    pattern = re.compile(rf"\b{re.escape(seat)}\b")
    for key in _FREE_TEXT_KEYS:
        val = resolved.get(key)
        if isinstance(val, str) and pattern.search(val):
            return val
    messages = resolved.get("messages")
    if isinstance(messages, list):
        for m in messages:
            if isinstance(m, str) and pattern.search(m):
                return m
    return None


class PlayerAgent:
    """Wraps one roster model as a game participant: issues a prompt, parses the
    required JSON fields back out, resolves any player-name fields to exact seats,
    and retries on malformed output before falling back to a random legal action.
    """

    def __init__(self, spec: ModelSpec, provider: ChatProvider, rules: dict):
        self.spec = spec
        self.provider = provider
        self.rules = rules

    def _maybe_remember(self, state: GameState, seat: str | None, resolved: dict) -> None:
        """Every player -- not just doctor/detective, who get engine-authored outcome
        notes -- can optionally carry a private note of their own into future turns via
        the "remember" field, fed back through build_system_prompt's private_notes
        rendering. Applied centrally here so every ask() call site gets it uniformly,
        without needing to touch each one in engine.py.
        """
        if not seat:
            return
        note = resolved.get("remember")
        if isinstance(note, str) and note.strip():
            state.get(seat).private_notes.append(f"(Day {state.day}, your own note) {note.strip()}")

    def _maybe_track_suspicions(self, state: GameState, seat: str | None, resolved: dict) -> None:
        """Structured sibling to _maybe_remember: a per-seat suspicion tracker instead
        of free-form prose, so a player's read on others persists as discrete updatable
        entries (fed back via build_system_prompt) rather than needing to be re-derived
        from scratch, or restated, every turn.
        """
        if not seat:
            return
        updates = resolved.get("suspicions")
        if not isinstance(updates, dict):
            return
        tracker = state.get(seat).suspicions
        for target_seat, read in updates.items():
            if isinstance(target_seat, str) and isinstance(read, str) and target_seat.strip() and read.strip():
                tracker[target_seat.strip()] = read.strip()

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
        max_tokens: int | None = None,
    ) -> dict:
        attempts = self.rules.get("max_format_retries", 2) + 1
        effective_user_prompt = user_prompt

        for attempt in range(1, attempts + 1):
            resp = self.provider.complete(
                system_prompt,
                effective_user_prompt,
                temperature=self.rules.get("temperature", 0.9),
                max_tokens=max_tokens if max_tokens is not None else self.rules.get("max_tokens", 500),
                timeout=self.rules.get("request_timeout_seconds", 60),
            )
            state.log_raw_call(
                seat=seat,
                model_key=self.spec.key,
                purpose=purpose,
                attempt=attempt,
                system_prompt=system_prompt,
                user_prompt=effective_user_prompt,
                response_text=resp.text,
                error=resp.error,
                cost_usd=resp.cost_usd,
            )
            # Track cost even on a failed/empty attempt: the provider still billed for
            # it (e.g. "empty_completion" -- reasoning tokens consumed, zero visible
            # content -- is still a real, paid call), so skipping this would silently
            # undercount spend.
            self._track_cost(state, resp)
            if resp.error:
                continue

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

            violation = _self_reference_violation(resolved, seat)
            if violation and attempt < attempts:
                # A real regenerate, not just another blind retry: the model gets told
                # exactly what it did wrong so the next attempt has a real chance of
                # fixing it, instead of hoping temperature alone shakes it loose.
                effective_user_prompt = (
                    f"{user_prompt}\n\nSYSTEM NOTE: your previous response referred to "
                    f"yourself as \"{seat}\" in the third person (\"{violation}\"). You "
                    f"are {seat} -- rewrite using \"I\"/\"me\" instead of your own seat "
                    "name. Try again."
                )
                continue

            self._maybe_remember(state, seat, resolved)
            self._maybe_track_suspicions(state, seat, resolved)
            return resolved

        state.note_format_failure(self.spec.key)
        fallback: dict = {
            "thought": "",
            "message": "(no response)",
            "messages": ["(no response)"],
            "speech": "(no response)",
        }
        if target_keys:
            for key, candidates in target_keys.items():
                if candidates:
                    fallback[key] = random.choice(candidates)
        return fallback
