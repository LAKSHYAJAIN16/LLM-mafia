from __future__ import annotations

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

        if resp.status_code != 200:
            return ProviderResponse(text="", error=f"http_{resp.status_code}: {resp.text[:300]}")

        data = resp.json()
        try:
            text = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError):
            return ProviderResponse(text="", error=f"unexpected_response_shape: {str(data)[:300]}")

        usage = data.get("usage", {})
        return ProviderResponse(
            text=text,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
        )
