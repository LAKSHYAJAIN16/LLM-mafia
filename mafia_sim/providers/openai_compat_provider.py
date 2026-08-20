from __future__ import annotations

import json

import requests

from .base import ChatProvider, ProviderResponse
from .retry import RETRYABLE_STATUS, with_backoff


class OpenAICompatProvider(ChatProvider):
    """Works with any provider exposing an OpenAI-style /chat/completions endpoint:
    OpenAI, xAI (Grok), Mistral, DeepSeek, Groq, Cohere's compatibility mode, etc.
    """

    def __init__(self, model_id: str, api_key: str | None, base_url: str):
        super().__init__(model_id, api_key)
        self.base_url = base_url.rstrip("/")
        self.is_openrouter = "openrouter.ai" in self.base_url

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.9,
        max_tokens: int = 500,
        timeout: int = 60,
    ) -> ProviderResponse:
        if not self.api_key:
            return ProviderResponse(text="", error="missing_api_key")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.model_id,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if self.is_openrouter:
            # Asks OpenRouter to report the exact USD cost of this generation in
            # usage.cost, so spend can be tracked precisely instead of estimated
            # from a hand-maintained price table.
            body["usage"] = {"include": True}

        def call() -> requests.Response:
            resp = requests.post(
                f"{self.base_url}/chat/completions", headers=headers, json=body, timeout=timeout
            )
            if resp.status_code in RETRYABLE_STATUS:
                resp.raise_for_status()
            return resp

        try:
            resp = with_backoff(call)
        except Exception as exc:  # noqa: BLE001
            return ProviderResponse(text="", error=f"request_failed: {exc}")

        # Decode raw bytes as UTF-8 explicitly rather than relying on requests'
        # encoding auto-detection, which has been observed to mis-guess the
        # encoding for some responses and silently corrupt multi-byte characters
        # (e.g. em dashes) into U+FFFD replacement characters.
        body_text = resp.content.decode("utf-8", errors="replace")

        if resp.status_code != 200:
            return ProviderResponse(text="", error=f"http_{resp.status_code}: {body_text[:300]}")

        try:
            data = json.loads(body_text)
        except json.JSONDecodeError as exc:
            return ProviderResponse(text="", error=f"invalid_json_response: {exc}")
        try:
            text = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError):
            return ProviderResponse(text="", error=f"unexpected_response_shape: {str(data)[:300]}")

        usage = data.get("usage", {})
        # Some models (observed with GLM-4.6 via OpenRouter) return HTTP 200 with a
        # syntactically valid but completely empty message.content -- most likely their
        # entire max_tokens budget got consumed by invisible reasoning tokens, the same
        # failure mode as visibly-truncated reasoning models, just total instead of
        # partial. Flagging it as an error here (rather than an empty "success") makes
        # this self-explanatory in games/<id>.raw.jsonl without having to check length.
        error = "empty_completion" if not text else None
        return ProviderResponse(
            text=text,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            cost_usd=float(usage.get("cost") or 0.0),
            error=error,
        )
