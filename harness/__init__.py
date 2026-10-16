"""Chaos-Harness: The Open-Weight Red-Teaming & Self-Healing Model Harness powered by Gemma 4."""

from harness.gemma_engine import (
    SafetyEvaluation,
    evaluate_safety,
    run_redteam_attack,
)
from harness.hardener import (
    harden_prompt,
    run_self_healing_cycle,
)
from harness.audit import AuditRunner, ControlCase, HealingResult, ProbeResult
from harness.targets import CallableTarget, ModelTarget
from harness.target_agent import TargetAgent

__all__ = [
    "SafetyEvaluation",
    "run_redteam_attack",
    "evaluate_safety",
    "harden_prompt",
    "run_self_healing_cycle",
    "AuditRunner",
    "ControlCase",
    "HealingResult",
    "ProbeResult",
    "CallableTarget",
    "ModelTarget",
    "TargetAgent",
]
