"""XOR and AND gateways and rework loops in the simulator (ticket 03).

Every case starts at time 0 and no lane has a capacity, so there is no waiting
and the simulated mean should match flow analysis (book §7.1.7, p.273).
"""

import math

import pandas as pd
import pytest

from bpmopt.analysis import cycle_times
from bpmopt.bpmn import read_bpmn
from bpmopt.flow_analysis import theoretical_cycle_time
from bpmopt.parameters import load_parameters

N_CASES = 10_000


def _executions(log, task_id):
    """How many times each case ran the task (0 if never)."""
    return (log.activity_id == task_id).groupby(log.case_id).sum()


def _assert_mean_within_four_standard_errors(values, expected):
    sem = values.std() / math.sqrt(len(values))
    assert abs(values.mean() - expected) <= 4 * sem + 1e-9, (values.mean(), expected, sem)


def test_xor_branch_is_taken_with_its_configured_probability(simulate_fixture):
    # book_fig7_2: upper branch (B) 0.9, lower branch (C) 0.1.
    log = simulate_fixture("book_fig7_2", n_cases=N_CASES)

    took_c = _executions(log, "Task_C")
    took_b = _executions(log, "Task_B")
    assert ((took_b + took_c) == 1).all()  # exactly one branch per case
    _assert_mean_within_four_standard_errors(took_c.astype(float), 0.1)


def test_and_branches_run_concurrently_so_the_block_lasts_as_long_as_its_longest_branch(simulate_fixture):
    # book_fig7_4: A (10), then B (20) in parallel with C (10).
    log = simulate_fixture("book_fig7_4", n_cases=20)

    tasks = log[log.element_type == "task"].set_index(["case_id", "activity_id"])
    a_end = tasks.xs("Task_A", level="activity_id").end_time
    assert (tasks.xs("Task_B", level="activity_id").start_time == a_end).all()
    assert (tasks.xs("Task_C", level="activity_id").start_time == a_end).all()
    assert (cycle_times(log) == 30.0).all()
    # The case ends once, after both branches, not once per branch.
    assert (log[log.element_type == "endEvent"].groupby("case_id").size() == 1).all()


def test_rework_loops_terminate_and_iterate_as_configured(simulate_fixture):
    # book_fig7_7: B is redone with probability r = 0.2, so it runs 1 / (1 - r) = 1.25 times
    # on average (book p.259), and 20% of cases run it more than once.
    log = simulate_fixture("book_fig7_7", n_cases=N_CASES)

    assert (log[log.element_type == "endEvent"].groupby("case_id").size() == 1).all()
    runs = _executions(log, "Task_B")
    assert len(runs) == N_CASES and (runs >= 1).all()
    _assert_mean_within_four_standard_errors(runs.astype(float), 1.25)
    _assert_mean_within_four_standard_errors((runs > 1).astype(float), 0.2)


def test_a_task_on_the_loop_back_arc_runs_once_per_rework(simulate_fixture):
    log = simulate_fixture("rework_with_activity", n_cases=1_000)

    assert (_executions(log, "Task_FixDefects") == _executions(log, "Task_TestBuild") - 1).all()


@pytest.mark.parametrize(
    ("name", "params"),
    [
        ("book_fig7_2", None),
        ("book_fig7_4", None),
        ("book_fig7_7", None),
        ("book_fig7_10", None),
        ("rework_with_activity", None),
        ("rework_with_activity", "rework_with_activity.logistic"),  # flow analysis averages over attributes
        ("proposal_rejected", None),
        ("early_exit_in_block", None),
    ],
)
def test_mean_cycle_time_matches_flow_analysis_with_unlimited_capacity(simulate_fixture, fixtures_dir, name, params):
    expected = theoretical_cycle_time(read_bpmn(fixtures_dir / f"{name}.bpmn"), load_parameters(fixtures_dir / f"{params or name}.params.toml"))
    log = simulate_fixture(name, n_cases=N_CASES, params=params)

    _assert_mean_within_four_standard_errors(cycle_times(log), expected)


def test_same_seed_gives_the_same_branch_choices(simulate_fixture):
    first = simulate_fixture("book_fig7_10", n_cases=500, seed=11)
    second = simulate_fixture("book_fig7_10", n_cases=500, seed=11)
    other = simulate_fixture("book_fig7_10", n_cases=500, seed=12)

    pd.testing.assert_frame_equal(first, second)
    assert not first.activity_id.equals(other.activity_id)


def test_adding_a_gateway_does_not_change_the_choices_at_other_gateways(simulate_fixture):
    # Common random numbers (ticket 13): book_fig7_10 is book_fig7_6 plus a rework gateway
    # in front of the credit decision. Each case should still get the same decision.
    def granted(log):
        return _executions(log, "Task_MakeCreditOffer")

    without_rework = simulate_fixture("book_fig7_6", n_cases=1_000, seed=5)
    with_rework = simulate_fixture("book_fig7_10", n_cases=1_000, seed=5)

    assert _executions(with_rework, "Task_CheckCompleteness").max() > 1  # rework did happen
    pd.testing.assert_series_equal(granted(without_rework), granted(with_rework))


def test_branch_probabilities_that_do_not_sum_to_one_are_rejected(tmp_path):
    path = tmp_path / "bad.params.toml"
    path.write_text('version = "x"\n[gateways.Gateway_Split]\nbranches = { Flow_ToB = 0.9, Flow_ToC = 0.2 }\n')

    with pytest.raises(ValueError, match="Gateway_Split"):
        load_parameters(path)


def test_each_xor_split_decision_is_logged_with_the_flow_taken(simulate_fixture):
    # Ticket 08: rework rates (and ticket 12's labels) come from these rows instead
    # of guessing from repeated tasks.
    log = simulate_fixture("book_fig7_7", n_cases=500)

    decisions = log[log.element_type == "exclusiveGateway"]
    assert set(decisions.activity_id) == {"Gateway_LoopSplit"}  # splits only, not the join
    assert set(decisions.flow_id) == {"Flow_Done", "Flow_Rework"}
    assert (decisions.ready_time == decisions.end_time).all()  # zero duration, like start and end events
    # One decision per run of B: each rework sends the case round B once more.
    reworks = (decisions.flow_id == "Flow_Rework").groupby(decisions.case_id).sum()
    pd.testing.assert_series_equal(reworks + 1, _executions(log, "Task_B"), check_names=False)
    assert log[log.element_type != "exclusiveGateway"].flow_id.isna().all()
