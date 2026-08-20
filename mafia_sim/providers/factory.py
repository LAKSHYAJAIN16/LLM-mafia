from __future__ import annotations

import os
from dataclasses import dataclass

import yaml

from .anthropic_provider import AnthropicProvider
from .base import ChatProvider
from .google_provider import GoogleProvider
from .mock_provider import MockProvider
from .openai_compat_provider import OpenAICompatProvider


@dataclass
class ModelSpec:
    key: str
    display_name: str
    provider: str
    model_id: str
    api_key_env: str | None = None
    base_url: str | None = None
    enabled: bool = True
    vendor: str = "unknown"  # company behind the model, e.g. "anthropic", "meta" -- used to
    # keep any two models from the same company out of the same game (see tournament.py)
    open_source: bool = False

    @property
    def has_api_key(self) -> bool:
        if self.provider == "mock":
            return True
        return bool(self.api_key_env and os.environ.get(self.api_key_env))


def load_model_specs(path: str) -> list[ModelSpec]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return [ModelSpec(**entry) for entry in data["models"]]


def build_provider(spec: ModelSpec) -> ChatProvider:
    api_key = os.environ.get(spec.api_key_env) if spec.api_key_env else None

    if spec.provider == "anthropic":
        return AnthropicProvider(spec.model_id, api_key)
    if spec.provider == "google":
        return GoogleProvider(spec.model_id, api_key)
    if spec.provider == "openai_compat":
        if not spec.base_url:
            raise ValueError(f"model '{spec.key}' uses openai_compat but has no base_url")
        return OpenAICompatProvider(spec.model_id, api_key, spec.base_url)
    if spec.provider == "mock":
        return MockProvider(spec.model_id, None)

    raise ValueError(f"unknown provider '{spec.provider}' for model '{spec.key}'")


def load_runnable_roster(path: str, require_keys: bool = True) -> dict[str, tuple[ModelSpec, ChatProvider]]:
    """Loads models.yaml and returns {key: (spec, provider)} for enabled models.

    If require_keys is True, models whose API key env var isn't set are skipped
    (with a note to stderr) rather than failing the whole load.
    """
    roster: dict[str, tuple[ModelSpec, ChatProvider]] = {}
    for spec in load_model_specs(path):
        if not spec.enabled:
            continue
        if require_keys and not spec.has_api_key:
            print(f"[roster] skipping '{spec.key}': env var {spec.api_key_env} not set")
            continue
        roster[spec.key] = (spec, build_provider(spec))
    return roster
