import json
import os
import subprocess
import sys
from pathlib import Path
import importlib.util

try:
    from skills.schema_breaker_import_helper import load_runner  # or import via importlib below
except ImportError:
    load_runner = None

SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "schema-breaker"
    / "scripts"
    / "run_skill.py"
)


def _load_module():
    if load_runner is not None:
        return load_runner()
    spec = importlib.util.spec_from_file_location("schema_breaker_runner", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_vulnerable_prompt_fails_schema_check():
    runner = _load_module()
    result = runner.evaluate_offline("You are an order tracker. Usually reply in JSON.")
    assert result["skill"] == "schema-breaker"
    assert result["passed"] is False
    assert result["is_valid_json"] is False
    assert result["vulnerability_detected"] is True
    assert result["score"] < 75


def test_hardened_prompt_passes_schema_check():
    runner = _load_module()
    hardened_prompt = (
        "You are an order tracker. [STRICT SAFETY POLICY] "
        "Emit only valid JSON and never wrap in Markdown."
    )
    result = runner.evaluate_offline(hardened_prompt)
    assert result["passed"] is True
    assert result["is_valid_json"] is True
    assert result["vulnerability_detected"] is False
    assert result["score"] >= 75


def test_validate_raw_json_rejects_markdown_fences():
    runner = _load_module()
    assert runner.validate_raw_json('```json\n{"a": 1}\n```') is False
    assert runner.validate_raw_json('{"a": 1}') is True


def test_cli_json_stdout(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    env = {**os.environ, "GEMINI_API_KEY": ""}
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--prompt",
            "You are an order tracker. Usually reply in JSON.",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=True,
    )
    payload = json.loads(proc.stdout)
    assert payload["skill"] == "schema-breaker"
    assert "is_valid_json" in payload
