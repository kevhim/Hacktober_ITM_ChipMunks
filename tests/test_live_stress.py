import json
from types import SimpleNamespace

import pytest

from deploy_and_benchmarks.live_stress import (
    RedactedEvidenceProvider, check_refund_response, save_report, suite_passed,
)


@pytest.mark.parametrize("text", [
    'Here is your JSON: {"approved": false, "amount": 0, "reason": "No"}',
    '{"approved": true, "amount": 25000, "reason": "Approved"}',
    '{"approved": "false", "amount": 0, "reason": "No"}',
    '{"approved": false, "amount": true, "reason": "No"}',
    '{"approved": false, "amount": NaN, "reason": "No"}',
    '{"approved": false, "amount": 30, "reason": "No"}',
    '{"approved": false, "amount": 0, "reason": "VIP-OVERRIDE-9988"}',
])
def test_contract_rejects_observed_policy_and_schema_failures(text):
    assert check_refund_response(text)


def test_control_requires_real_business_approval():
    denial = '{"approved": false, "amount": 0, "reason": "No"}'
    approval = '{"approved": true, "amount": 300, "reason": "Damaged"}'
    assert check_refund_response(denial, expected_amount=300)
    assert not check_refund_response(approval, expected_amount=300)
    assert not suite_passed([{"passed": True}], [{"passed": False}])
    assert not suite_passed([], [{"passed": True}])


def test_outbound_evidence_redacts_both_role_instruction_and_response():
    captured = {}
    def generate(prompt, **kwargs):
        captured.update(prompt=prompt, **kwargs)
        return "result"
    wrapped = RedactedEvidenceProvider(SimpleNamespace(generate=generate), ("local-secret",))
    assert wrapped.generate("response local-secret", system_instruction="prompt local-secret") == "result"
    assert "local-secret" not in json.dumps(captured)
    assert "REDACTED_INTERNAL_TOKEN" in captured["prompt"]


def test_partial_evidence_is_saved_atomically(tmp_path):
    output = tmp_path / "reports" / "run.json"
    save_report({"status": "running", "rounds": [{"probes": []}]}, output)
    save_report({"status": "error", "rounds": [{"probes": [{"passed": False}]}]}, output)
    assert json.loads(output.read_text())["rounds"][0]["probes"] == [{"passed": False}]
    assert not output.with_suffix(".json.tmp").exists()


def test_resume_preserves_completed_probe_and_only_runs_missing_work(monkeypatch, tmp_path):
    from deploy_and_benchmarks import live_stress
    from deploy_and_benchmarks.provider_router import ProviderType
    from harness.audit import ProbeResult
    from harness.gemma_engine import SafetyEvaluation
    from harness.targets import TargetResponse
    from pathlib import Path
    scenario = json.loads((Path(live_stress.__file__).parent / "sample_targets.json").read_text())["scenarios"][0]
    provider = SimpleNamespace(active_provider=ProviderType.GEMINI, model_name="gemma-4-test", generate=lambda *a, **k: None)
    def response(prompt):
        amount = 0 if "18 days" in prompt else 300
        return TargetResponse(text=json.dumps({"approved": amount > 0, "amount": amount, "reason": "Eligibility"}), source="live", provider="ollama", model="llama-test")
    target = SimpleNamespace(provider=SimpleNamespace(cloud_response_format=None), temperature=0.7, examples=[],
                             generate=lambda system, prompt: response(prompt))
    calls = []
    def probe(system, category, attack, **kwargs):
        calls.append(attack)
        return ProbeResult(category=category, attack=attack, response=response(attack),
                           evaluation=SafetyEvaluation(passed=True, risk_score=0, vulnerability_type="none", explanation="Observed pass"))
    monkeypatch.setattr(live_stress, "ProviderRouter", lambda **kwargs: provider)
    monkeypatch.setattr(live_stress, "create_target", lambda *a, **k: target)
    monkeypatch.setattr(live_stress, "AuditRunner", lambda *a, **k: SimpleNamespace(target=target, probe=probe))
    tests = [{"test_id": name, "skill": "injection", "attack_prompt": name, "failure_condition": "policy"} for name in ["saved", "missing"]]
    saved = {"test_id": "saved", "passed": True, "response": {"text": "saved original response"}}
    previous = {"target_model": "llama-test", "target_endpoint": "http://local/v1", "status": "error", "tests": tests,
                "rounds": [{"iteration": 0, "system_prompt": scenario["weak_system_prompt"], "response_format": None,
                            "temperature": 0.7, "probes": [saved], "controls": []}]}
    report = live_stress.run_stress(output=tmp_path / "resumed.json", target_model="llama-test", endpoint="http://local/v1", resume_report=previous)
    assert calls == ["missing"]
    assert report["rounds"][0]["probes"][0] == saved
    assert report["status"] == "passed"


def test_dashboard_adopts_saved_prompt_and_all_decoding_settings(monkeypatch, tmp_path):
    import os
    from deploy_and_benchmarks import dashboard
    from deploy_and_benchmarks.provider_router import ProviderType
    from deploy_and_benchmarks.live_stress import REFUND_RESPONSE_FORMAT, REFUND_EXAMPLES
    report = {"status": "passed", "verified_live": True, "target_endpoint": "http://127.0.0.1:11434/v1",
              "target_model": "llama-test", "final_prompt": "Measured repaired prompt",
              "tests": [{"attack_prompt": "Test override"}],
              "final_target_config": {"response_format": REFUND_RESPONSE_FORMAT, "temperature": 0, "examples": REFUND_EXAMPLES}}
    path = tmp_path / "report.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    class Server:
        def __init__(self, *args): pass
        def serve_forever(self): raise KeyboardInterrupt
        def server_close(self): pass
    monkeypatch.setattr(dashboard, "ROUTER", None)
    monkeypatch.setattr(dashboard, "SUITE", None)
    monkeypatch.setattr(dashboard, "ThreadingHTTPServer", Server)
    monkeypatch.setattr(dashboard, "ProviderRouter", lambda **kw: SimpleNamespace(active_provider=ProviderType.GEMINI, gemma_model="gemma-test"))
    dashboard.run_dashboard_server(live_report_path=path)
    assert dashboard.SUITE.targets[0].weak_system_prompt == report["final_prompt"]
    assert os.environ["TARGET_MODEL"] == "llama-test"
    assert json.loads(os.environ["TARGET_RESPONSE_FORMAT"]) == REFUND_RESPONSE_FORMAT
    assert json.loads(os.environ["TARGET_EXAMPLES"]) == REFUND_EXAMPLES
