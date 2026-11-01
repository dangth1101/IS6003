"""Baseline metrics from the event log (ticket 08), tested on simulator logs with known parameters."""

import math

import pytest

from bpmopt.analysis import baseline_metrics, flow_analysis_check, mean_cycle_time
from bpmopt.bpmn import read_bpmn
from bpmopt.parameters import load_parameters


@pytest.fixture
def baseline(simulate_fixture, fixtures_dir):
    def run(name, params=None, n_cases=2_000, seed=42):
        log = simulate_fixture(name, n_cases=n_cases, seed=seed, params=params)
        return baseline_metrics(log, read_bpmn(fixtures_dir / f"{name}.bpmn"))

    return run


@pytest.mark.parametrize("name", ["sequence", "book_fig7_10"])
def test_cycle_time_efficiency_is_one_when_nothing_waits(baseline, name):
    # Book §7.1.2 (p.262): CTE = TCT / CT. With unlimited capacity no task waits, so
    # every case is processing for its whole cycle time. book_fig7_10 has rework and an
    # AND-block: parallel work must count once, not twice.
    metrics = baseline(name)

    assert metrics["cycle_time_efficiency"] == pytest.approx(1.0)
    assert metrics["waiting_time"]["mean"] == pytest.approx(0.0, abs=1e-9)
    assert metrics["processing_time"] == pytest.approx(metrics["cycle_time"])


def test_waiting_lowers_cycle_time_efficiency_but_not_processing_time(baseline):
    # sequence.capacity2: two developers at about 79% utilisation, so cases queue.
    # Durations are fixed (2 + 5.5 + 3), so processing time per case stays 10.5 days.
    metrics = baseline("sequence", params="sequence.capacity2")

    assert metrics["processing_time"] == pytest.approx({"mean": 10.5, "median": 10.5, "p90": 10.5})
    assert metrics["waiting_time"]["mean"] > 1.0
    assert metrics["cycle_time"]["mean"] == pytest.approx(10.5 + metrics["waiting_time"]["mean"])
    assert metrics["cycle_time_efficiency"] == pytest.approx(10.5 / metrics["cycle_time"]["mean"])
    assert metrics["cycle_time_efficiency"] < 0.9


def _within_four_standard_errors(rate, p, n):
    return abs(rate - p) <= 4 * math.sqrt(p * (1 - p) / n)


@pytest.mark.parametrize(
    ("name", "gateway", "r"),
    [("book_fig7_7", "Gateway_LoopSplit", 0.2), ("rework_with_activity", "Gateway_LoopSplit", 0.25), ("book_fig7_10", "Gateway_CompletenessSplit", 0.2)],
)
def test_rework_rate_recovers_the_configured_loop_back_probability(baseline, name, gateway, r):
    # A case loops back at least once exactly when its first pass loops back, so the
    # share of cases with any rework estimates r.
    metrics = baseline(name, n_cases=10_000)

    rates = {row["gateway_id"]: row["rate"] for row in metrics["rework"]}
    # Only rework gateways: book_fig7_10's credit decision is an XOR-split but not a loop.
    assert set(rates) == {gateway}
    assert _within_four_standard_errors(rates[gateway], r, 10_000), rates


def test_rework_rate_counts_only_the_cases_that_reach_the_gateway(baseline):
    # proposal_rejected: 20% of proposals are rejected and never reach testing. The test
    # loop's rate is still its configured r = 0.25, not 0.8 x 0.25.
    metrics = baseline("proposal_rejected", n_cases=10_000)

    rates = {row["gateway_id"]: row["rate"] for row in metrics["rework"]}
    assert set(rates) == {"Gateway_ReviewSplit", "Gateway_TestSplit"}
    assert _within_four_standard_errors(rates["Gateway_ReviewSplit"], 0.25, 10_000)
    assert _within_four_standard_errors(rates["Gateway_TestSplit"], 0.25, 8_000)


def test_waiting_by_activity_is_highest_at_the_tightest_lane(baseline):
    # three_lanes: testers run at 85% utilisation, analysts and developers at 50%.
    metrics = baseline("three_lanes", n_cases=5_000)

    waiting = metrics["waiting_by_activity"]
    assert {row["activity_id"] for row in waiting} == {"Task_WriteSpec", "Task_BuildApp", "Task_TestApp"}
    assert waiting[0]["activity_id"] == "Task_TestApp"
    assert [row["mean"] for row in waiting] == sorted((row["mean"] for row in waiting), reverse=True)
    # Testers are one server with Poisson arrivals and a fixed 1.7-day task, about M/D/1:
    # Wq = rho x s / (2 (1 - rho)) = 0.85 x 1.7 / 0.3, about 4.8 days. Upstream lanes
    # smooth the arrivals a little, so allow a wide margin.
    assert waiting[0]["mean"] == pytest.approx(4.8, rel=0.3)
    assert waiting[0]["mean"] > 5 * waiting[1]["mean"]


def test_flow_analysis_check_reruns_the_model_with_unlimited_capacity(simulate_fixture, fixtures_dir):
    # three_lanes queues at the testers, so the logged cycle time is well above the
    # book's flow analysis value (2 + 4 + 1.7 = 7.7). The check drops the capacities,
    # as the book requires for the comparison (§7.1.7, p.273), and then they agree.
    model = read_bpmn(fixtures_dir / "three_lanes.bpmn")
    params = load_parameters(fixtures_dir / "three_lanes.params.toml")
    log = simulate_fixture("three_lanes", n_cases=1_000)

    check = flow_analysis_check(model, params, n_cases=1_000, seed=42)

    assert check["theoretical"] == pytest.approx(7.7)
    assert check["simulated"] == pytest.approx(7.7)
    assert mean_cycle_time(log) > 9.0
