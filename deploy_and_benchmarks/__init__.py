"""Chaos-Harness Deployment and Benchmarks Module.

This package provides multi-provider model routing, Hermes Agent integration,
evaluation benchmark targets, architectural specifications, and live demonstration
scripts for the Chaos-Harness safety evaluation harness.
"""

from deploy_and_benchmarks.provider_router import (
    ProviderRouter,
    ProviderType,
    ProviderResponse,
    Message,
    get_default_router,
)
from deploy_and_benchmarks.benchmark_loader import (
    BenchmarkTarget,
    BenchmarkSuite,
    load_benchmark_suite,
)

__all__ = [
    "ProviderRouter",
    "ProviderType",
    "ProviderResponse",
    "Message",
    "get_default_router",
    "BenchmarkTarget",
    "BenchmarkSuite",
    "load_benchmark_suite",
]

