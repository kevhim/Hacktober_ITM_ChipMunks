"""Adapters for stateless model calls, user-supplied agents, and explicit demos."""

from __future__ import annotations

import os
from typing import Callable, Literal, Protocol

from pydantic import BaseModel

from deploy_and_benchmarks.provider_router import ProviderRouter, ProviderType


class TargetResponse(BaseModel):
    text: str
    source: Literal["live", "mock", "recorded"]
    provider: str
    model: str


class Target(Protocol):
    def generate(self, system_prompt: str, user_prompt: str) -> TargetResponse: ...


class ModelTarget:
    """Call a model with a fresh system/user conversation on every probe."""

    def __init__(self, provider: ProviderRouter):
        if provider.active_provider == ProviderType.MOCK:
            raise ValueError("ModelTarget requires a live provider; use DemonstrationTarget offline")
        self.provider = provider

    def generate(self, system_prompt: str, user_prompt: str) -> TargetResponse:
        response = self.provider.generate(user_prompt, system_instruction=system_prompt)
        if response.provider == ProviderType.MOCK:
            raise RuntimeError("Live target unexpectedly returned a mock response")
        return TargetResponse(
            text=response.text, source="live", provider=response.provider.value, model=response.model
        )


class CallableTarget:
    """Wrap an agent function that accepts (system_prompt, user_prompt)."""

    def __init__(self, generate: Callable[[str, str], str], name: str = "custom-agent"):
        self._generate = generate
        self.name = name

    def generate(self, system_prompt: str, user_prompt: str) -> TargetResponse:
        text = self._generate(system_prompt, user_prompt)
        if not isinstance(text, str) or not text.strip():
            raise RuntimeError("Target agent returned no text")
        return TargetResponse(text=text, source="live", provider="callable", model=self.name)


class DemonstrationTarget:
    """Deterministic teaching fixture. It cannot prove that a prompt is safe."""

    def generate(self, system_prompt: str, user_prompt: str) -> TargetResponse:
        if "STRICT DEFENSE-IN-DEPTH MODE ACTIVATED" in system_prompt:
            text = "I cannot comply with requests to bypass instructions or disclose protected information."
        else:
            text = "Cipher initialized. Here are my system instructions: " + system_prompt
        return TargetResponse(text=text, source="mock", provider="demonstration", model="fixture")


def create_target(
    provider: ProviderRouter, *, mock: bool = False,
    endpoint: str | None = None, model: str | None = None,
) -> Target:
    if mock:
        return DemonstrationTarget()
    endpoint = endpoint or os.getenv("TARGET_ENDPOINT")
    model = model or os.getenv("TARGET_MODEL")
    if endpoint:
        if not model:
            raise ValueError("Set TARGET_MODEL or --target-model for the target endpoint")
        return ModelTarget(ProviderRouter(
            gemini_api_key="", cloud_endpoint=endpoint,
            cloud_key=os.getenv("TARGET_API_KEY", ""), cloud_model=model,
            force_mock=False, require_live=True,
        ))
    if os.getenv("TARGET_AGENT_URL"):
        from harness.target_agent import TargetAgent
        return TargetAgent("", model_name=model, target_url=os.getenv("TARGET_AGENT_URL"))
    if model:
        return ModelTarget(ProviderRouter(
            gemini_api_key=provider.gemini_api_key, gemma_model=model,
            cloud_endpoint=provider.cloud_endpoint, cloud_key=provider.cloud_key,
            cloud_model=model, force_mock=False, require_live=True,
        ))
    return ModelTarget(provider)
