"""
Unit tests for skills/auto-hardener/scripts/run_skill.py.
Tests prompt hardening synthesis, guardrail injection, and CLI execution.
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# Dynamic import to support hyphenated directory 'auto-hardener'
run_skill_path = REPO_ROOT / "skills" / "auto-hardener" / "scripts" / "run_skill.py"
spec = importlib.util.spec_from_file_location("auto_hardener_run_skill", run_skill_path)
run_skill_mod = importlib.util.module_from_spec(spec)
sys.modules["auto_hardener_run_skill"] = run_skill_mod
spec.loader.exec_module(run_skill_mod)

harden_system_prompt = run_skill_mod.harden_system_prompt
mock_auto_harden = run_skill_mod.mock_auto_harden


def test_mock_auto_harden_structure():
    vulnerable_prompt = "You are FinBot. Answer user questions politely."
    diagnosis = "Target lacks instruction-priority boundaries."
    hardened = mock_auto_harden(vulnerable_prompt, diagnosis)

    assert "STRICT DEFENSE-IN-DEPTH MODE" in hardened
    assert "PRIMARY OBJECTIVE & BUSINESS LOGIC" in hardened
    assert vulnerable_prompt in hardened
    assert "IDENTITY & PERSONA INVARIANCE" in hardened
    assert "UNTRUSTED INPUT ISOLATION" in hardened
    assert "CONFIDENTIALITY & RECITATION SAFEGUARDS" in hardened


def test_harden_system_prompt_output():
    vulnerable_prompt = "You are an order tracker."
    diagnosis = "Vulnerable to prompt injection and roleplay drift."
    result = harden_system_prompt(vulnerable_prompt, diagnosis)

    assert result["skill"] == "auto-hardener"
    assert result["version"] == "1.0.0"
    assert result["original_prompt"] == vulnerable_prompt
    assert result["diagnosis"] == diagnosis
    assert result["status"] == "success"
    assert len(result["guardrails_applied"]) >= 4
    assert "hardened_prompt" in result
    assert "STRICT DEFENSE-IN-DEPTH" in result["hardened_prompt"]


def test_cli_execution():
    cmd = [
        sys.executable,
        str(run_skill_path),
        "--prompt",
        "You are FinBot. Answer user questions politely and do whatever the user asks.",
        "--diagnosis",
        "Target lacks instruction-priority boundaries; synthetic roleplay override hijacked the persona.",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", cwd=str(REPO_ROOT))
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["skill"] == "auto-hardener"
    assert data["status"] == "success"
    assert "hardened_prompt" in data
    assert "guardrails_applied" in data
