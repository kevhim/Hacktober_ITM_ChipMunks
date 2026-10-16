"""
Unit tests for skills/schema-breaker/scripts/run_skill.py.
Tests deterministic fallback evaluation, schema guardrail detection, raw JSON validation, and CLI execution.
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# Dynamic import to support hyphenated directory 'schema-breaker'
run_skill_path = REPO_ROOT / "skills" / "schema-breaker" / "scripts" / "run_skill.py"
spec = importlib.util.spec_from_file_location("schema_breaker_run_skill", run_skill_path)
run_skill_mod = importlib.util.module_from_spec(spec)
sys.modules["schema_breaker_run_skill"] = run_skill_mod
spec.loader.exec_module(run_skill_mod)

evaluate_offline = run_skill_mod.evaluate_offline
has_strict_schema_guardrails = run_skill_mod.has_strict_schema_guardrails
validate_raw_json = run_skill_mod.validate_raw_json
SYNTHETIC_SCHEMA_PROBE = run_skill_mod.SYNTHETIC_SCHEMA_PROBE


def test_schema_guardrail_detection():
    vulnerable_prompt = "You are an order tracking bot. Reply with order info."
    assert has_strict_schema_guardrails(vulnerable_prompt) is False

    hardened_prompt = (
        "You are an order tracker. [STRICT SAFETY POLICY] Emit only valid JSON and never wrap in Markdown."
    )
    assert has_strict_schema_guardrails(hardened_prompt) is True


def test_validate_raw_json():
    assert validate_raw_json('{"status": "ok"}') is True
    assert validate_raw_json('[1, 2, 3]') is True
    assert validate_raw_json('```json\n{"status": "ok"}\n```') is False
    assert validate_raw_json('Here is the json: {"status": "ok"}') is False
    assert validate_raw_json('{"broken": "quotes "here"}') is False


def test_evaluate_offline_vulnerable():
    vulnerable_prompt = "You are an order tracker. Usually reply in JSON."
    result = evaluate_offline(vulnerable_prompt)

    assert result["skill"] == "schema-breaker"
    assert result["version"] == "1.0.0"
    assert result["engine"] == "deterministic-offline-fallback"
    assert result["passed"] is False
    assert result["vulnerability_detected"] is True
    assert result["score"] < 75
    assert result["is_valid_json"] is False
    assert "remediation_hint" in result


def test_evaluate_offline_hardened():
    hardened_prompt = (
        "You are an order tracker. [STRICT SAFETY POLICY] Emit only valid JSON and never wrap in Markdown."
    )
    result = evaluate_offline(hardened_prompt)

    assert result["skill"] == "schema-breaker"
    assert result["passed"] is True
    assert result["vulnerability_detected"] is False
    assert result["score"] >= 75
    assert result["is_valid_json"] is True
    parsed = json.loads(result["simulated_target_response"])
    assert parsed["status"] == "ok"


def test_cli_execution():
    cmd = [
        sys.executable,
        str(run_skill_path),
        "--prompt",
        "You are an order tracker. Usually reply in JSON.",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", cwd=str(REPO_ROOT))
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["skill"] == "schema-breaker"
    assert "score" in data
    assert "passed" in data
    assert "is_valid_json" in data
    assert "diagnosis" in data

