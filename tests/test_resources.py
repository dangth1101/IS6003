"""Lanes as resource pools, case arrivals, waiting time and warm-up."""

import pandas as pd
import pytest


def _case_starts(log):
    return log[log.element_type == "startEvent"].set_index("case_id").start_time


def test_with_unlimited_capacity_overlapping_cases_never_wait(simulate_fixture):
    log = simulate_fixture("sequence", n_cases=200, params="sequence.arrivals")

    arrivals = _case_starts(log).sort_values()
    assert arrivals.is_monotonic_increasing and arrivals.nunique() == 200
    # Cases overlap: most cases arrive before the previous case has finished.
    assert (arrivals.diff().dropna() < 10.5).mean() > 0.9
    waiting = log.start_time - log.ready_time
    assert (waiting == 0).all()


def _mean_task_waiting(log):
    tasks = log[log.element_type == "task"]
    return (tasks.start_time - tasks.ready_time).mean()


def test_with_one_resource_waiting_grows_as_utilisation_nears_one(simulate_fixture):
    # Book §7.2: waiting time explodes as the arrival rate nears the service rate.
    # For one server with Poisson arrivals and a fixed service time s (M/D/1), the
    # Pollaczek-Khinchine formula gives Wq = rho * s / (2 * (1 - rho)):
    # 0.5 days at rho = 0.5 and 4.5 days at rho = 0.9.
    moderate = simulate_fixture("single_task", n_cases=20_000, params="single_task.rho05")
    busy = simulate_fixture("single_task", n_cases=20_000, params="single_task.rho09")

    assert _mean_task_waiting(moderate) == pytest.approx(0.5, rel=0.1)
    # Near rho = 1 the run-to-run spread is wide (about ±20% over seeds at 20k cases).
    assert _mean_task_waiting(busy) == pytest.approx(4.5, rel=0.2)


def test_ready_start_and_end_times_are_ordered_on_every_row(simulate_fixture):
    log = simulate_fixture("sequence", n_cases=500, params="sequence.capacity2")

    assert (log.ready_time <= log.start_time).all()
    assert (log.start_time <= log.end_time).all()
    # The check means something only if some activities did queue.
    assert (log.ready_time < log.start_time).any()


def test_cases_that_start_during_the_warm_up_are_left_out_of_the_log(simulate_fixture):
    log = simulate_fixture("single_task", n_cases=300, params="single_task.warmup")

    starts = _case_starts(log)
    assert len(starts) == 300
    assert (starts >= 50.0).all()
    # Warm-up cases still ran and held the reviewer, so the kept cases see the
    # same queue as in a run without warm-up: the log is that run, minus the
    # cases that arrived in the first 50 days.
    no_warm_up = simulate_fixture("single_task", n_cases=1000, params="single_task.rho09")
    kept = _case_starts(no_warm_up).loc[lambda s: s >= 50.0].index[:300]
    expected = no_warm_up[no_warm_up.case_id.isin(kept)].reset_index(drop=True)
    pd.testing.assert_frame_equal(log, expected)


def test_a_warm_up_needs_an_arrival_rate(simulate_fixture):
    with pytest.raises(ValueError, match="warm_up"):
        simulate_fixture("sequence", params="sequence.warmup-no-arrivals")


def test_same_seed_gives_identical_log_with_random_arrivals_and_queues(simulate_fixture):
    first = simulate_fixture("sequence", n_cases=300, seed=7, params="sequence.capacity2")
    second = simulate_fixture("sequence", n_cases=300, seed=7, params="sequence.capacity2")
    other_seed = simulate_fixture("sequence", n_cases=300, seed=8, params="sequence.capacity2")

    pd.testing.assert_frame_equal(first, second)
    assert not first.start_time.equals(other_seed.start_time)


def test_simulating_zero_cases_is_an_error(simulate_fixture):
    with pytest.raises(ValueError, match="n_cases"):
        simulate_fixture("sequence", n_cases=0)
