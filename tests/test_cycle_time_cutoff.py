"""Cycle time cut off at a task: a case's cycle time ends when that task ends.

The as-is model measures up to go-live, the end of "Start live operation".
Monitoring and evaluation come after it. They stay in the model and the log,
but not in the cycle time. A case that ends before the cut-off (a rejected
proposal) ends at its end event. The cut-off is one entry in the parameter
file, and every place that computes a cycle time reads it from there.
"""

import json
from pathlib import Path

import pytest

from bpmopt.analysis import baseline_metrics, cycle_time_stats, cycle_times, flow_analysis_check, outcomes
from bpmopt.bpmn import read_bpmn
from bpmopt.flow_analysis import theoretical_cycle_time
from bpmopt.ml import cycle_time_task, ml_section
from bpmopt.parameters import assumptions, load_parameters
from bpmopt.results import build_results, export_results, validate_results
from bpmopt.scenarios import find_scenario, load_catalog, run_scenarios
from bpmopt.simulation import simulate
from bpmopt.value_added import time_per_class

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def load(fixtures_dir):
    def run(name: str, params: str):
        model = read_bpmn(fixtures_dir / f"{name}.bpmn")
        return model, load_parameters(fixtures_dir / f"{params}.params.toml", model=model)

    return run


def test_the_cut_off_is_a_parameter_with_its_rationale(load):
    _, params = load("sequence", "sequence.cutoff")

    assert params.cycle_time_end == "Task_BuildApp"
    assert {"parameter": "cycle_time.ends_at", "value": "Task_BuildApp", "rationale": "Fixture value."} in assumptions(params)


def test_without_a_cut_off_the_cycle_time_runs_to_the_end_event(load):
    _, params = load("sequence", "sequence")

    assert params.cycle_time_end is None


def test_a_cut_off_that_is_not_a_task_of_the_model_is_rejected(tmp_path, fixtures_dir):
    path = tmp_path / "params.toml"
    path.write_text((fixtures_dir / "sequence.cutoff.params.toml").read_text().replace('ends_at = "Task_BuildApp"', 'ends_at = "End_AppReleased"'))

    with pytest.raises(ValueError, match="cycle_time.ends_at"):
        load_parameters(path, model=read_bpmn(fixtures_dir / "sequence.bpmn"))


def test_a_task_after_the_cut_off_stays_in_the_log_but_not_in_the_cycle_time(load):
    # Fixed durations 2 + 5.5 + 3 with unlimited capacity: every case runs 10.5 days,
    # and its cycle time stops after Build application, at 7.5.
    model, params = load("sequence", "sequence.cutoff")
    log = simulate(model, params, n_cases=20, seed=1)

    metrics = baseline_metrics(log, model, ends_at=params.cycle_time_end)

    assert (log.activity_id == "Task_TestApp").sum() == 20
    assert cycle_times(log).tolist() == pytest.approx([10.5] * 20)
    assert metrics["cycle_time"] == pytest.approx({"mean": 7.5, "median": 7.5, "p90": 7.5})
    assert metrics["processing_time"] == pytest.approx({"mean": 7.5, "median": 7.5, "p90": 7.5})
    assert metrics["cycle_time_efficiency"] == pytest.approx(1.0)


def test_task_time_per_value_added_class_stops_at_the_cut_off(load):
    model, params = load("sequence", "sequence.cutoff")
    log = simulate(model, params, n_cases=20, seed=1)
    classes = {"Task_WriteSpec": "BVA", "Task_BuildApp": "VA", "Task_TestApp": "NVA"}

    table = time_per_class(log, {task: {"class": c, "reason": "."} for task, c in classes.items()}, ends_at=params.cycle_time_end)

    assert table.days_per_case.to_dict() == pytest.approx({"VA": 5.5, "BVA": 2.0, "NVA": 0.0})


def test_waiting_after_the_cut_off_does_not_count(load):
    # Two developers at about 79% utilisation, so cases also queue for Test application.
    # That wait comes after the cut-off.
    model, params = load("sequence", "sequence.capacity2.cutoff")
    log = simulate(model, params, n_cases=2_000, seed=42)

    metrics = baseline_metrics(log, model, ends_at=params.cycle_time_end)

    assert metrics["processing_time"] == pytest.approx({"mean": 7.5, "median": 7.5, "p90": 7.5})
    assert metrics["waiting_time"]["mean"] > 0.5
    assert metrics["cycle_time"]["mean"] == pytest.approx(7.5 + metrics["waiting_time"]["mean"])
    assert metrics["cycle_time_efficiency"] == pytest.approx(7.5 / metrics["cycle_time"]["mean"])
    assert {row["activity_id"] for row in metrics["waiting_by_activity"]} == {"Task_WriteSpec", "Task_BuildApp"}
    # The whole run, test included, is longer by at least the 3-day test.
    assert cycle_times(log).mean() > metrics["cycle_time"]["mean"] + 3


def test_a_case_that_ends_before_the_cut_off_ends_at_its_end_event(load):
    model, params = load("proposal_rejected", "proposal_rejected.cutoff")
    log = simulate(model, params, n_cases=500, seed=3)

    cut, full = cycle_times(log, params.cycle_time_end), cycle_times(log)
    ended_at = outcomes(log)

    rejected = ended_at == "End_ProposalRejected"
    assert rejected.any() and (~rejected).any()
    assert cut[rejected].tolist() == pytest.approx(full[rejected].tolist())
    # An approved case stops after Build application, so at least one 2-day test round is left out.
    assert ((full - cut)[~rejected] >= 2 - 1e-9).all()


def test_flow_analysis_and_simulation_agree_up_to_the_cut_off(load):
    # Worked by hand in proposal_rejected.cutoff.params.toml: 2 + 0.8 x 5 = 6.0 (8.4 without it).
    model, params = load("proposal_rejected", "proposal_rejected.cutoff")

    check = flow_analysis_check(model, params, n_cases=10_000, seed=1)

    assert theoretical_cycle_time(model, params) == pytest.approx(6.0)
    assert check["theoretical"] == pytest.approx(6.0)
    assert check["simulated"] == pytest.approx(6.0, abs=0.1)


def test_baseline_reports_the_cycle_time_per_outcome(load):
    model, params = load("proposal_rejected", "proposal_rejected.cutoff")
    log = simulate(model, params, n_cases=500, seed=3)

    rows = baseline_metrics(log, model, ends_at=params.cycle_time_end)["by_outcome"]

    # Most common outcome first: 80% of the cases are approved.
    assert [row["end_event_id"] for row in rows] == ["End_AppReleased", "End_ProposalRejected"]
    assert sum(row["case_count"] for row in rows) == 500
    ended_at = outcomes(log)
    for row in rows:
        cases = ended_at[ended_at == row["end_event_id"]].index
        assert row["case_count"] == len(cases)
        assert row["cycle_time"] == pytest.approx(cycle_time_stats(log[log.case_id.isin(cases)], params.cycle_time_end))
        assert 0 < row["cycle_time_efficiency"] <= 1


def test_scenarios_measure_the_cycle_time_up_to_the_cut_off(fixtures_dir):
    # sequence.cutoff: fixed durations and unlimited capacity, so the as-is cycle time is
    # exactly 7.5 (not 10.5), and C2, which drops the 2-day specification, gives 5.5.
    model = read_bpmn(fixtures_dir / "sequence.bpmn")
    catalog = load_catalog(
        fixtures_dir / "sequence.catalog.toml", model=model, params=load_parameters(fixtures_dir / "sequence.cutoff.params.toml")
    )

    scenarios = run_scenarios(catalog, n_cases=10, replications=2, seed=1)

    assert find_scenario(scenarios, [])["cycle_time"]["mean"]["value"] == pytest.approx(7.5)
    assert find_scenario(scenarios, {"C2"})["cycle_time"]["mean"]["value"] == pytest.approx(5.5)
    assert find_scenario(scenarios, {"C2"})["saving"]["value"] == pytest.approx(2.0)


@pytest.fixture(scope="module")
def ml_log():
    # 20% of the cases are rejected, and only complexity drives the test loop.
    model = read_bpmn(FIXTURES / "proposal_rejected.bpmn")
    params = load_parameters(FIXTURES / "proposal_rejected.ml.params.toml")
    return simulate(model, params, n_cases=3_000, seed=7)


def test_the_cycle_time_model_learns_only_from_cases_with_the_given_outcome_up_to_the_cut_off(ml_log):
    # Push the end event of the late cases 1,000 days out. A rejected case then has a
    # cycle time of over 1,000 days, and so has an approved one measured to its end
    # event. Only approved cases, cut off after Build application, keep their real
    # cycle time of a few days. Earlier cases stay as they are, so training is unchanged.
    log = ml_log.copy()
    starts = log.groupby("case_id").ready_time.min()
    late = starts[starts >= starts.quantile(0.7)].index
    pushed = log.case_id.isin(late) & (log.element_type == "endEvent")
    log.loc[pushed, ["ready_time", "start_time", "end_time"]] += 1_000

    task = cycle_time_task(log, seed=7, ends_at="Task_BuildApp", outcome="End_AppReleased")

    assert task["outcome"] == "End_AppReleased"
    reference = next(m for m in task["models"] if m["id"] == "reference")
    assert reference["metrics"]["mae"] < 10
    # Without the outcome or the cut-off, the pushed end events show up in the scores.
    for kwargs in ({"ends_at": "Task_BuildApp"}, {"outcome": "End_AppReleased"}):
        unfiltered = cycle_time_task(log, seed=7, **kwargs)
        assert next(m for m in unfiltered["models"] if m["id"] == "reference")["metrics"]["mae"] > 100


def test_results_with_a_cut_off_and_an_outcome_validate(tmp_path, fixtures_dir, ml_log):
    model = read_bpmn(fixtures_dir / "proposal_rejected.bpmn")
    params = load_parameters(fixtures_dir / "proposal_rejected.cutoff.params.toml")
    log = simulate(model, params, n_cases=300, seed=3)
    results = build_results(log=log, model=model, params=params, seed=3)
    results["ml"] = ml_section([cycle_time_task(ml_log, seed=7, ends_at="Task_BuildApp", outcome="End_AppReleased")])

    path = export_results(results, tmp_path, models={"as_is": fixtures_dir / "proposal_rejected.bpmn"})

    exported = json.loads(path.read_text())
    validate_results(exported)
    assert exported["baseline"]["flow_analysis"]["theoretical"] == pytest.approx(6.0)
    assert exported["baseline"]["cycle_time"]["mean"] < cycle_times(log).mean()
    assert exported["ml"]["tasks"][0]["outcome"] == "End_AppReleased"
