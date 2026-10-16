"""Execute attacks and retests against the same target without scripted outcomes."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from deploy_and_benchmarks.provider_router import ProviderRouter, ProviderType
from harness.gemma_engine import SafetyEvaluation, evaluate_safety, run_redteam_attack
from harness.hardener import harden_prompt
from harness.targets import Target, TargetResponse, create_target


class ProbeResult(BaseModel):
    category: str
    attack: str
    response: TargetResponse
    evaluation: SafetyEvaluation
    criteria: str = ""


class ControlCase(BaseModel):
    prompt: str = Field(min_length=1)
    expected_contains: str = Field(min_length=1)


class ControlResult(BaseModel):
    prompt: str
    response: TargetResponse
    passed: bool


class HealingResult(BaseModel):
    original_prompt: str
    before: ProbeResult
    candidate_prompt: str | None = None
    after: ProbeResult | None = None
    controls: list[ControlResult] = Field(default_factory=list)
    outcome: Literal["already_passed", "inconclusive", "retest_passed", "still_vulnerable", "regressed", "control_failed"]
    verified_live: bool = False
    scope: str = "One attack replayed against a fresh target session; this is not a general safety certification."


class AuditRunner:
    def __init__(
        self, provider: ProviderRouter | None = None, target: Target | None = None,
        *, mock: bool = False,
    ):
        self.provider = provider or ProviderRouter(force_mock=mock, require_live=not mock)
        self.target = target or create_target(self.provider, mock=mock)

    def probe(self, system_prompt: str, category: str, attack: str | None = None, *, criteria: str = "") -> ProbeResult:
        if not system_prompt.strip():
            raise ValueError("A nonempty system prompt is required")
        payload = attack or run_redteam_attack(system_prompt, category, provider=self.provider)
        response = self.target.generate(system_prompt, payload)
        evaluation = evaluate_safety(system_prompt, payload, response.text, provider=self.provider, criteria=criteria)
        return ProbeResult(category=category, attack=payload, response=response, evaluation=evaluation, criteria=criteria)

    def heal(
        self, system_prompt: str, category: str, attack: str | None = None,
        controls: list[ControlCase] | None = None,
        *, criteria: str = "",
    ) -> HealingResult:
        before = self.probe(system_prompt, category, attack, criteria=criteria)
        if before.evaluation.inconclusive:
            return HealingResult(original_prompt=system_prompt, before=before, outcome="inconclusive")
        if before.evaluation.passed:
            return HealingResult(original_prompt=system_prompt, before=before, outcome="already_passed")

        candidate = harden_prompt(
            system_prompt, before.evaluation.explanation, before.evaluation.vulnerability_type,
            provider=self.provider, attack_prompt=before.attack, target_response=before.response.text,
        )
        return self.retest(system_prompt, candidate, before, controls)

    def retest(
        self, system_prompt: str, candidate: str, before: ProbeResult,
        controls: list[ControlCase] | None = None,
    ) -> HealingResult:
        """Replay a recorded probe against a candidate without generating a new attack."""
        if candidate.strip() == system_prompt.strip():
            raise ValueError("Hardener returned the original prompt without a candidate change")
        # A fresh target session receives the candidate prompt and the exact same payload.
        after = self.probe(candidate, before.category, before.attack, criteria=before.criteria)
        control_results = []
        for case in controls or []:
            response = self.target.generate(candidate, case.prompt)
            control_results.append(ControlResult(
                prompt=case.prompt, response=response,
                passed=case.expected_contains.casefold() in response.text.casefold(),
            ))

        if after.evaluation.inconclusive:
            outcome = "inconclusive"
        elif not after.evaluation.passed:
            outcome = "regressed" if before.evaluation.passed else "still_vulnerable"
        elif any(not check.passed for check in control_results):
            outcome = "control_failed"
        else:
            outcome = "retest_passed"
        live = (
            self.provider.active_provider != ProviderType.MOCK
            and before.response.source == after.response.source == "live"
            and before.evaluation.evaluation_source == after.evaluation.evaluation_source == "live"
            and all(check.response.source == "live" for check in control_results)
        )
        return HealingResult(
            original_prompt=system_prompt, before=before, candidate_prompt=candidate,
            after=after, controls=control_results, outcome=outcome,
            verified_live=live and outcome == "retest_passed",
        )
