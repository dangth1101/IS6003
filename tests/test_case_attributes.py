"""Case attributes, attribute-dependent branching and triangular durations in the simulator (ticket 07)."""

import math

import pandas as pd
import pytest

from bpmopt.analysis import cycle_times
from bpmopt.bpmn import read_bpmn
from bpmopt.flow_analysis import theoretical_cycle_time
from bpmopt.parameters import load_parameters

ATTRIBUTES = ["project_type", "complexity", "integrations", "workload"]


def test_every_log_row_carries_the_attributes_of_its_case(simulate_fixture):
    log = simulate_fixture("sequence", n_cases=200, params="sequence.attributes")

    assert set(ATTRIBUTES) <= set(log.columns)
    assert log[ATTRIBUTES].notna().all().all()
    # Drawn once per case, so they never change within a case.
    assert (log.groupby("case_id")[ATTRIBUTES].nunique() == 1).all().all()
    cases = log.groupby("case_id")[ATTRIBUTES].first()
    assert set(cases.project_type) == {"web", "mobile", "core"}
    assert set(cases.complexity) == {1, 2, 3}
    assert (cases.integrations >= 0).all() and cases.integrations.nunique() > 2
    assert cases.workload.between(0.2, 1.0).all()


# logistic(-2 + 1 x complexity + 1.5 x [mobile]), worked out by hand.
FAIL_PROBABILITY = {
    (1, "web"): 0.2689,  # logistic(-1)
    (2, "web"): 0.5,  # logistic(0)
    (3, "web"): 0.7311,  # logistic(1)
    (1, "mobile"): 0.6225,  # logistic(0.5)
    (2, "mobile"): 0.8176,  # logistic(1.5)
    (3, "mobile"): 0.9241,  # logistic(2.5)
}


def test_complex_and_mobile_projects_fail_testing_more_often(simulate_fixture):
    log = simulate_fixture("rework_with_activity", n_cases=10_000, params="rework_with_activity.logistic")

    for (complexity, project_type), p in FAIL_PROBABILITY.items():
        group = log[(log.complexity == complexity) & (log.project_type == project_type)]
        # Every test round is one decision at the split; every failed one is followed by a fix.
        rounds = (group.activity_id == "Task_TestBuild").sum()
        failed = (group.activity_id == "Task_FixDefects").sum()
        assert abs(failed / rounds - p) <= 4 * math.sqrt(p * (1 - p) / rounds), (complexity, project_type, failed / rounds, p)


def test_triangular_durations_stay_in_range_and_average_to_their_mean(simulate_fixture, fixtures_dir):
    log = simulate_fixture("sequence", n_cases=5_000, params="sequence.triangular")

    tasks = log[log.element_type == "task"]
    durations = (tasks.end_time - tasks.start_time).groupby(tasks.activity_id)
    low = pd.Series({"Task_WriteSpec": 1.0, "Task_BuildApp": 3.0, "Task_TestApp": 1.0})
    high = pd.Series({"Task_WriteSpec": 3.0, "Task_BuildApp": 10.0, "Task_TestApp": 6.0})
    assert (durations.min() >= low[durations.min().index]).all()
    assert (durations.max() <= high[durations.max().index]).all()
    # Flow analysis uses the triangular mean (min + mode + max) / 3: 2 + 6 + 3 = 11 days.
    params = load_parameters(fixtures_dir / "sequence.triangular.params.toml")
    assert theoretical_cycle_time(read_bpmn(fixtures_dir / "sequence.bpmn"), params) == pytest.approx(11.0)
    ct = cycle_times(log)
    assert abs(ct.mean() - 11.0) <= 4 * ct.std() / math.sqrt(len(ct))


# 4 x (1 + 0.5 x complexity + 1 x [mobile]), worked out by hand.
BUILD_DAYS = {
    (1, "web"): 6.0,
    (3, "web"): 10.0,
    (1, "core"): 6.0,
    (2, "mobile"): 12.0,
    (3, "mobile"): 14.0,
}


def test_a_scaled_duration_grows_with_the_case_attributes(simulate_fixture):
    log = simulate_fixture("sequence", n_cases=500, params="sequence.scaled")

    builds = log[log.activity_id == "Task_BuildApp"]
    for (complexity, project_type), days in BUILD_DAYS.items():
        group = builds[(builds.complexity == complexity) & (builds.project_type == project_type)]
        assert len(group) > 0
        assert (group.end_time - group.start_time).to_numpy() == pytest.approx(days), (complexity, project_type)
    # Tasks without a scale don't change.
    specs = log[log.activity_id == "Task_WriteSpec"]
    assert (specs.end_time - specs.start_time).to_numpy() == pytest.approx(2.0)


def test_flow_analysis_uses_the_mean_of_a_scaled_duration_over_the_attribute_distributions(fixtures_dir):
    params = load_parameters(fixtures_dir / "sequence.scaled.params.toml")

    # 2 + 4 x (1 + 0.5 x 1.9 + 1 x 0.3) + 3 = 14 days.
    assert theoretical_cycle_time(read_bpmn(fixtures_dir / "sequence.bpmn"), params) == pytest.approx(14.0)
