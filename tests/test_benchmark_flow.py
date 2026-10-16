from deploy_and_benchmarks.benchmark_loader import run_benchmark_verification


def test_offline_benchmarks_report_evidence_without_live_verification():
    report = run_benchmark_verification(mock=True)
    assert report["total_targets_evaluated"] == 5
    assert report["status"] == "completed"
    assert not report["all_live_retests_passed"]
    assert all(result["before"]["response"]["source"] == "mock" for result in report["evaluations"])
