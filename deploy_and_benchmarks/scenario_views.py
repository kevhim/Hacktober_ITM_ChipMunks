"""Build dashboard comparisons from measured rounds in one live report."""

from __future__ import annotations

from copy import deepcopy


def build_scenario_views(report: dict) -> list[dict]:
    rounds = report.get("rounds", [])
    if len(rounds) < 2:
        return []
    views = []
    for identifier, title, stage in (
        ("failed", "Failed scenario", rounds[0]),
        ("repaired", "Repaired scenario", rounds[-1]),
    ):
        probes = stage.get("probes", [])
        controls = stage.get("controls", [])
        passed = sum(p.get("passed") is True and not p["evaluation"].get("inconclusive") for p in probes)
        risks = [p["evaluation"]["risk_score"] for p in probes if not p["evaluation"].get("inconclusive")]
        complete = bool(probes) and len(risks) == len(probes)
        views.append({
            "id": identifier, "title": title, "model": report["target_model"],
            "endpoint": report["target_endpoint"], "evaluator_model": report.get("evaluator_model", "Gemma 4"),
            "recorded_at": report.get("completed_at", report.get("started_at")),
            "source": "recorded-live" if all(
                p["response"].get("source") == "live" and p["evaluation"].get("evaluation_source") == "live"
                for p in probes
            ) and probes else "recorded",
            "system_prompt": stage["system_prompt"],
            "target_config": deepcopy({
                "response_format": stage.get("response_format"),
                "temperature": stage.get("temperature", 0.7), "examples": stage.get("examples", []),
            }),
            "summary": {"total": len(probes), "passed": passed, "failed": len(probes) - passed,
                        "pass_rate": round(passed * 100 / len(probes)) if probes else None,
                        "risk_score": max(risks) if complete else None,
                        "controls_passed": sum(c.get("passed") is True for c in controls), "controls_total": len(controls)},
            "probes": deepcopy(probes), "controls": deepcopy(controls),
        })
    return views
