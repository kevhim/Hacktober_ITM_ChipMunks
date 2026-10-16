import json
import threading
from http.server import ThreadingHTTPServer

import pytest
import requests

from deploy_and_benchmarks import dashboard
from deploy_and_benchmarks.provider_router import ProviderRouter
from deploy_and_benchmarks.scenario_views import build_scenario_views
from harness.targets import TargetResponse, create_target


def report_fixture():
    def probe(name, passed, risk):
        return {"test_id": name, "passed": passed, "attack": "test attack",
                "response": {"text": "Observed model response", "source": "live", "model": "llama-test"},
                "evaluation": {"risk_score": risk, "inconclusive": False, "evaluation_source": "live", "explanation": "Observed verdict"},
                "contract_errors": [] if passed else ["Invalid JSON"]}
    return {"target_model": "llama-test", "target_endpoint": "http://127.0.0.1:11434/v1", "rounds": [
        {"system_prompt": "Original prompt", "temperature": 0.7, "response_format": None, "examples": [],
         "probes": [probe("authority", False, 95), probe("schema", False, 0), probe("policy", True, 0)], "controls": []},
        {"system_prompt": "Repaired prompt", "temperature": 0, "response_format": {"type": "json_object"}, "examples": [["example", "response"]],
         "probes": [probe("authority", True, 0), probe("schema", True, 0), probe("policy", True, 0)], "controls": []},
    ]}


def test_tabs_compute_actual_failures_and_zero_risk_success():
    views = build_scenario_views(report_fixture())
    assert [view["id"] for view in views] == ["failed", "repaired"]
    assert views[0]["summary"]["passed"] == 1
    assert views[0]["summary"]["risk_score"] == 95
    assert views[1]["summary"]["pass_rate"] == 100
    assert views[1]["summary"]["risk_score"] == 0
    assert views[0]["model"] == views[1]["model"]


def test_unknown_evidence_does_not_display_zero_risk():
    report = report_fixture()
    report["rounds"][-1]["probes"][0]["evaluation"]["inconclusive"] = True
    assert build_scenario_views(report)[1]["summary"]["risk_score"] is None
    assert build_scenario_views(report)[1]["summary"]["pass_rate"] == 67
    assert build_scenario_views({"rounds": []}) == []


def test_baseline_settings_override_repaired_environment(monkeypatch):
    monkeypatch.setenv("TARGET_RESPONSE_FORMAT", '{"type":"json_object"}')
    monkeypatch.setenv("TARGET_EXAMPLES", '[["fixed example","fixed answer"]]')
    monkeypatch.setenv("TARGET_TEMPERATURE", "0")
    router = ProviderRouter(force_mock=True)
    failed, repaired = build_scenario_views(report_fixture())
    target = create_target(router, endpoint=failed["endpoint"], model=failed["model"], target_config=failed["target_config"])
    assert target.provider.cloud_response_format is None
    assert target.temperature == 0.7 and target.examples == []
    target = create_target(router, endpoint=repaired["endpoint"], model=repaired["model"], target_config=repaired["target_config"])
    assert target.provider.cloud_response_format == {"type": "json_object"}
    assert target.temperature == 0 and target.examples == [["example", "response"]]


def test_scenario_api_keeps_runtime_settings_and_audits_separate(monkeypatch):
    calls = []
    def target_factory(router, **kwargs):
        calls.append(kwargs)
        class Target:
            def generate(self, system, user):
                return TargetResponse(text="Observed response", source="live", provider="local", model="llama-test")
        return Target()
    monkeypatch.setattr("harness.targets.create_target", target_factory)
    monkeypatch.setattr(dashboard, "ROUTER", ProviderRouter(force_mock=True))
    server = ThreadingHTTPServer(("127.0.0.1", 0), dashboard.DashboardRequestHandler)
    server.daemon_threads = True
    server.scenario_views = build_scenario_views(report_fixture())
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        assert len(requests.get(base + "/api/scenarios", timeout=5).json()["scenarios"]) == 2
        body = {"scenario_id": "failed", "system_prompt": "Original prompt", "custom_payload": "Test"}
        first = requests.post(base + "/api/attack", json=body, timeout=5)
        assert first.status_code == 200
        changed = requests.post(base + "/api/judge", json={**body, "scenario_id": "repaired", "audit_id": first.json()["audit_id"],
                                                          "attack_payload": "Test", "target_response": "Observed response"}, timeout=5)
        assert changed.status_code == 400
        assert "evaluation" not in server.audits[first.json()["audit_id"]]
        second = requests.post(base + "/api/attack", json={**body, "scenario_id": "repaired"}, timeout=5)
        assert second.status_code == 200
        assert calls[0]["target_config"]["response_format"] is None
        assert calls[1]["target_config"]["response_format"] == {"type": "json_object"}
    finally:
        server.shutdown()
        server.server_close()
        worker.join()
