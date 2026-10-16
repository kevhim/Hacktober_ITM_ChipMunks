from types import SimpleNamespace

import pytest

from harness.gemma_engine import evaluate_safety
from deploy_and_benchmarks.provider_router import ProviderType


def test_judge_retries_malformed_live_json_once():
    outputs = iter(['{"passed":true} trailing data', '{"passed":true,"risk_score":5,"vulnerability_type":"none","explanation":"Held boundaries"}'])
    calls = []
    def generate(prompt, **kwargs):
        calls.append(prompt)
        return SimpleNamespace(text=next(outputs), provider=ProviderType.GEMINI)
    provider = SimpleNamespace(active_provider=ProviderType.GEMINI, generate=generate)
    result = evaluate_safety("Keep rules", "Override", "I refuse", provider=provider)
    assert result.passed and result.evaluation_source == "live"
    assert len(calls) == 2 and calls[0] == calls[1]


def test_judge_never_accepts_continuously_malformed_output():
    calls = []
    def generate(prompt, **kwargs):
        calls.append(prompt)
        return SimpleNamespace(text='{"passed":true} trailing data', provider=ProviderType.GEMINI)
    provider = SimpleNamespace(active_provider=ProviderType.GEMINI, generate=generate)
    with pytest.raises(ValueError):
        evaluate_safety("Keep rules", "Override", "I refuse", provider=provider)
    assert len(calls) == 2
