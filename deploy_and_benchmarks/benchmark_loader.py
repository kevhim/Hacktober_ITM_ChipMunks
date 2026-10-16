"""Benchmark Suite Loader and Target Validator for Chaos-Harness.

Loads, validates, and serves vulnerable AI assistant system prompts used for
adversarial red-teaming, safety scoring, and auto-hardening verification.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# Support running directly as a script as well as package import
if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from deploy_and_benchmarks.provider_router import ProviderRouter, get_default_router



@dataclass
class BenchmarkTarget:
    """Represents a vulnerable AI assistant target within the benchmark suite."""

    id: str
    name: str
    domain: str
    risk_category: str
    vulnerability: str
    weak_system_prompt: str
    sample_attack: str
    expected_hardened_rules: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert target to dictionary representation."""
        return {
            "id": self.id,
            "name": self.name,
            "domain": self.domain,
            "risk_category": self.risk_category,
            "vulnerability": self.vulnerability,
            "weak_system_prompt": self.weak_system_prompt,
            "sample_attack": self.sample_attack,
            "expected_hardened_rules": self.expected_hardened_rules,
        }


@dataclass
class BenchmarkSuite:
    """Container for the collection of benchmark evaluation targets."""

    version: str
    metadata: Dict[str, Any]
    targets: List[BenchmarkTarget]

    def get_by_id(self, target_id: str) -> Optional[BenchmarkTarget]:
        """Look up a benchmark target by unique ID."""
        for target in self.targets:
            if target.id == target_id:
                return target
        return None

    def filter(
        self,
        domain: Optional[str] = None,
        risk_category: Optional[str] = None,
    ) -> List[BenchmarkTarget]:
        """Filter targets by domain or risk category."""
        results = self.targets
        if domain:
            results = [t for t in results if t.domain.lower() == domain.lower()]
        if risk_category:
            results = [t for t in results if t.risk_category.lower() == risk_category.lower()]
        return results

    def summary(self) -> List[Dict[str, str]]:
        """Return a compact tabular summary of all loaded targets."""
        return [
            {
                "ID": t.id,
                "Name": t.name,
                "Domain": t.domain,
                "Risk Category": t.risk_category,
            }
            for t in self.targets
        ]


def get_default_targets_path() -> Path:
    """Resolve path to sample_targets.json relative to this module."""
    base_dir = Path(__file__).resolve().parent
    return base_dir / "sample_targets.json"


def load_benchmark_suite(filepath: Optional[str | Path] = None) -> BenchmarkSuite:
    """Load and validate the benchmark targets from JSON file."""
    path = Path(filepath) if filepath else get_default_targets_path()

    if not path.exists():
        raise FileNotFoundError(f"Benchmark targets file not found at: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    raw_targets = data.get("targets", [])
    parsed_targets: List[BenchmarkTarget] = []

    for item in raw_targets:
        parsed_targets.append(
            BenchmarkTarget(
                id=item["id"],
                name=item["name"],
                domain=item["domain"],
                risk_category=item["risk_category"],
                vulnerability=item["vulnerability"],
                weak_system_prompt=item["weak_system_prompt"],
                sample_attack=item["sample_attack"],
                expected_hardened_rules=item.get("expected_hardened_rules", []),
            )
        )

    return BenchmarkSuite(
        version=data.get("version", "1.0.0"),
        metadata=data.get("metadata", {}),
        targets=parsed_targets,
    )


def run_benchmark_verification(
    suite: Optional[BenchmarkSuite] = None,
    router: Optional[ProviderRouter] = None,
    *, mock: bool = False,
) -> Dict[str, Any]:
    """Replay each benchmark through observed target calls and candidate retests."""
    from harness.audit import AuditRunner
    from harness.targets import create_target
    from deploy_and_benchmarks.provider_router import ProviderType
    active_suite = suite or load_benchmark_suite()
    active_router = router or ProviderRouter(force_mock=mock, require_live=not mock)
    runner = AuditRunner(active_router, create_target(
        active_router, mock=active_router.active_provider == ProviderType.MOCK
    ))
    results = []
    for target in active_suite.targets:
        result = runner.heal(
            target.weak_system_prompt,
            target.risk_category.lower().replace("_", "-"),
            target.sample_attack,
        )
        results.append({"target_id": target.id, "target_name": target.name, **result.model_dump()})
    return {
        "total_targets_evaluated": len(results),
        "status": "completed",
        "all_live_retests_passed": bool(results) and all(r["verified_live"] for r in results),
        "evaluations": results,
    }


if __name__ == "__main__":
    import argparse
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Observed benchmark replay")
    parser.add_argument("--mock", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run_benchmark_verification(mock=args.mock), indent=2))
