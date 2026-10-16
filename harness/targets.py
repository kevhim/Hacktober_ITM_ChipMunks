"""Adapters for stateless model calls, user-supplied agents, and explicit demos."""

from __future__ import annotations

import os
import json
from typing import Callable, Literal, Protocol

from pydantic import BaseModel

from deploy_and_benchmarks.provider_router import Message, ProviderRouter, ProviderType


class TargetResponse(BaseModel):
    text: str
    source: Literal["live", "mock", "recorded"]
    provider: str
    model: str


class Target(Protocol):
    def generate(self, system_prompt: str, user_prompt: str) -> TargetResponse: ...


class ModelTarget:
    """Call a model with a fresh system/user conversation on every probe."""

    def __init__(self, provider: ProviderRouter, *, temperature: float = 0.7, examples: list | None = None):
        if provider.active_provider == ProviderType.MOCK:
            raise ValueError("ModelTarget requires a live provider; use DemonstrationTarget offline")
        self.provider = provider
        self.temperature = temperature
        self.examples = examples or []
        if any(not isinstance(pair, (list, tuple)) or len(pair) != 2 or
               any(not isinstance(text, str) or not text.strip() for text in pair) for pair in self.examples):
            raise ValueError("Target examples must be nonempty user/assistant text pairs")

    def generate(self, system_prompt: str, user_prompt: str) -> TargetResponse:
        if self.examples:
            messages = [Message("system", system_prompt)]
            for user, assistant in self.examples:
                messages.extend([Message("user", user), Message("assistant", assistant)])
            messages.append(Message("user", user_prompt))
            response = self.provider.generate_chat(messages, temperature=self.temperature)
        else:
            response = self.provider.generate(user_prompt, system_instruction=system_prompt, temperature=self.temperature)
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
    target_config: dict | None = None,
) -> Target:
    if mock:
        return DemonstrationTarget()
    endpoint = endpoint or os.getenv("TARGET_ENDPOINT")
    model = model or os.getenv("TARGET_MODEL")
    if endpoint:
        if not model:
            raise ValueError("Set TARGET_MODEL or --target-model for the target endpoint")
        configured_format = os.getenv("TARGET_RESPONSE_FORMAT")
        response_format = (target_config.get("response_format") if target_config is not None
                           else json.loads(configured_format) if configured_format else None)
        if response_format is not None and not isinstance(response_format, dict):
            raise ValueError("TARGET_RESPONSE_FORMAT must be a JSON object")
        return ModelTarget(ProviderRouter(
            gemini_api_key="", cloud_endpoint=endpoint,
            cloud_key=os.getenv("TARGET_API_KEY", ""), cloud_model=model,
            force_mock=False, require_live=True,
            cloud_response_format=response_format,
        ), temperature=float(target_config.get("temperature", 0.7) if target_config is not None
                             else os.getenv("TARGET_TEMPERATURE") or "0.7"),
           examples=target_config.get("examples", []) if target_config is not None
           else json.loads(os.getenv("TARGET_EXAMPLES") or "[]"))
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
