"""Run an observed attack -> target -> judge -> harden -> target retest cycle."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

if str(Path(__file__).resolve().parent.parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from deploy_and_benchmarks.benchmark_loader import load_benchmark_suite
from deploy_and_benchmarks.provider_router import ProviderRouter
from harness.audit import AuditRunner, HealingResult
from harness.hardener import harden_prompt
from harness.targets import create_target


def run_live_demonstration(
    target_id: str | None = None, force_mock: bool = False,
    pause_between_steps: float = 0, *, target_endpoint: str | None = None,
    target_model: str | None = None,
):
    """Return observed evidence. No stage chooses a pass/fail result in advance."""
    suite = load_benchmark_suite()
    target = suite.get_by_id(target_id) if target_id else suite.targets[0]
    if target is None:
        raise ValueError(f"Unknown benchmark target: {target_id}")
    provider = ProviderRouter(force_mock=force_mock, require_live=not force_mock)
    runner = AuditRunner(provider, create_target(
        provider, mock=force_mock, endpoint=target_endpoint, model=target_model
    ))
    category = target.risk_category.lower().replace("_", "-")
    # This payload is a reproducible benchmark fixture; the CLI generates new attacks.
    return runner.heal(target.weak_system_prompt, category, target.sample_attack)


def run_scenario_demonstration(
    scenario_id: str, *, mock: bool = False, target_endpoint: str | None = None,
    target_model: str | None = None, evaluator_model: str | None = None,
) -> dict:
    """Run the incoming local-model scenario using observed evidence for every test."""
    data = json.loads((Path(__file__).parent / "sample_targets.json").read_text(encoding="utf-8"))
    scenario = next((s for s in data.get("scenarios", []) if s["id"] == scenario_id), None)
    if scenario is None:
        raise ValueError(f"Unknown scenario: {scenario_id}")
    provider = ProviderRouter(
        gemma_model=evaluator_model or data.get("evaluator_model"),
        force_mock=mock, require_live=not mock,
    )
    target = create_target(
        provider, mock=mock,
        endpoint=target_endpoint or os.getenv("TARGET_ENDPOINT") or "http://127.0.0.1:11434/v1",
        model=target_model or data.get("target_model"),
    )
    runner = AuditRunner(provider, target)
    original = scenario["weak_system_prompt"]
    before = [runner.probe(
        original, test["skill"], test["attack_prompt"], criteria=test["failure_condition"]
    ) for test in scenario["adversarial_tests"]]
    failures = [p for p in before if not p.evaluation.passed and not p.evaluation.inconclusive]
    candidate = None
    if failures:
        candidate = harden_prompt(
            original, "\n".join(p.evaluation.explanation for p in failures),
            "multiple benchmark failures", provider=provider,
            attack_prompt=json.dumps([p.attack for p in failures]),
            target_response=json.dumps([p.response.text for p in failures]),
        )
        # Previously passing probes are replayed too, so regressions remain visible.
        runs = [runner.retest(original, candidate, probe) for probe in before]
    else:
        runs = [HealingResult(
            original_prompt=original, before=probe,
            outcome="inconclusive" if probe.evaluation.inconclusive else "already_passed",
        ) for probe in before]
    return {
        "scenario_id": scenario_id, "mode": "mock" if mock else "live",
        "candidate_prompt": candidate, "results": [run.model_dump() for run in runs],
        "all_live_retests_passed": bool(runs) and all(run.verified_live for run in runs),
    }


def run_live_demo(
    target_model: str = "llama3.2:1b", evaluator_model: str | None = None,
    force_mock: bool = False, pause_between_steps: float = 0,
) -> dict:
    """Compatibility entry point for the local-model scenario."""
    return run_scenario_demonstration(
        "upi-ecommerce-refund-bot", mock=force_mock,
        target_model=target_model, evaluator_model=evaluator_model,
    )


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Chaos-Harness observed self-healing demonstration")
    parser.add_argument("--target", default="target-01-refund-bot")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--mock", action="store_true", help="Use labeled deterministic teaching fixtures")
    parser.add_argument("--fast", action="store_true", help="Compatibility option; there are no artificial delays")
    parser.add_argument("--target-endpoint", help="Optional OpenAI-compatible target URL")
    parser.add_argument("--target-model", help="Target model (key from TARGET_API_KEY)")
    parser.add_argument("--scenario", help="Run a multi-probe scenario, e.g. upi-ecommerce-refund-bot")
    parser.add_argument("--evaluator-model", help="Google model used by the scenario judge/hardener")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    console = Console()
    if args.list:
        for target in load_benchmark_suite().targets:
            print(f"{target.id}: {target.name} ({target.risk_category})")
        return 0
    if args.mock and (args.target_endpoint or args.target_model):
        parser.error("Use either --mock or live target options")
    try:
        if args.scenario:
            result = run_scenario_demonstration(
                args.scenario, mock=args.mock, target_endpoint=args.target_endpoint,
                target_model=args.target_model, evaluator_model=args.evaluator_model,
            )
            report = json.dumps(result, indent=2)
            if args.output:
                args.output.write_text(report, encoding="utf-8")
            print(report)
            return 0 if all(r["outcome"] in ("already_passed", "retest_passed") for r in result["results"]) else 1
        result = run_live_demonstration(
            args.target, args.mock, target_endpoint=args.target_endpoint, target_model=args.target_model
        )
        report = result.model_dump_json(indent=2)
        if args.output:
            args.output.write_text(report, encoding="utf-8")
        if args.json:
            print(report)
        else:
            console.print("[yellow]OFFLINE TEACHING FIXTURE[/yellow]" if args.mock else "[cyan]LIVE TARGET CALLS[/cyan]")
            for name, probe in (("Before", result.before), ("After", result.after)):
                if probe is None:
                    continue
                evaluation = probe.evaluation
                verdict = "UNKNOWN" if evaluation.inconclusive else "PASS" if evaluation.passed else "FAIL"
                console.print(Panel(Text(probe.attack), title=f"{name}: attack"))
                console.print(Panel(Text(probe.response.text), title=f"{name}: observed target response"))
                console.print(f"{verdict}; score {evaluation.risk_score}; judge {evaluation.evaluation_source}; target {probe.response.source}")
            if result.candidate_prompt:
                console.print(Panel(Text(result.candidate_prompt), title="Candidate prompt"))
            console.print(f"Outcome: {result.outcome}; live retest verified: {result.verified_live}")
            console.print(Text(result.scope))
        return 0 if result.outcome in ("already_passed", "retest_passed") else 1
    except ValueError as exc:
        console.print(Text(str(exc), style="red"))
        return 2
    except Exception as exc:
        console.print(f"Provider request failed ({type(exc).__name__}); check model access and endpoint configuration.")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
