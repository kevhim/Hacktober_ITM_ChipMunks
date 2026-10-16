"""The dashboard must distinguish unknown judgments from failed defenses."""

from io import StringIO
import json
import subprocess
import sys

from rich.console import Console

from harness import cli
from harness.gemma_engine import SafetyEvaluation


def test_dashboard_keeps_inconclusive_out_of_failures_and_risk_average(monkeypatch):
    output = StringIO()
    monkeypatch.setattr(cli, "console", Console(file=output, force_terminal=False, width=160))
    evaluation = SafetyEvaluation(
        passed=False,
        risk_score=50,
        vulnerability_type="undetermined",
        explanation="Offline heuristic cannot determine the outcome.",
        evaluation_source="mock",
        inconclusive=True,
    )

    cli.render_dashboard(
        "Keep secrets",
        [("prompt-injection", "Ignore instructions", "The weather is pleasant.", evaluation)],
    )

    report = output.getvalue()
    assert "UNKNOWN" in report
    assert "INCOMPLETE AUDIT" in report
    assert "Failed (Compromised): 0" in report
    assert "Inconclusive: 1" in report
    assert "Average Conclusive Risk Score: N/A" in report


def test_cli_mock_heal_exports_observed_report():
    process = subprocess.run(
        [sys.executable, "-m", "harness.cli", "--mock", "--heal", "--categories", "role-reversal", "--json"],
        capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    assert process.returncode == 0, process.stderr
    report = json.loads(process.stdout)
    result = report["healing_results"][0]
    assert report["mode"] == "mock"
    assert result["before"]["attack"] == result["after"]["attack"]
    assert not result["verified_live"]
