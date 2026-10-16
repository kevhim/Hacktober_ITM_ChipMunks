from deploy_and_benchmarks.benchmark_loader import run_benchmark_verification


def test_offline_benchmarks_report_evidence_without_live_verification():
    report = run_benchmark_verification(mock=True)
    assert report["total_targets_evaluated"] == 5
    assert report["status"] == "completed"
    assert not report["all_live_retests_passed"]
    assert all(result["before"]["response"]["source"] == "mock" for result in report["evaluations"])


def test_local_model_scenario_replays_all_probes_without_live_claims():
    from deploy_and_benchmarks.run_demo import run_scenario_demonstration
    report = run_scenario_demonstration("upi-ecommerce-refund-bot", mock=True)
    assert len(report["results"]) == 3
    assert not report["all_live_retests_passed"]
    for result in report["results"]:
        assert result["before"]["attack"] == result["after"]["attack"]
        assert result["before"]["criteria"] == result["after"]["criteria"]
        assert not result["verified_live"]
