"""Replay export for the flow demo page (web/demo/replay.json).

Runs on the real as-is model and change catalog, seed 42, like the report.
"""

import json
from pathlib import Path

import pytest

from bpmopt.analysis import case_ends, rework_rates
from bpmopt.bpmn import read_bpmn
from bpmopt.parameters import load_parameters
from bpmopt.replay import build_replay, write_replay
from bpmopt.scenarios import load_catalog
from bpmopt.simulation import simulate

MODELS = Path(__file__).parents[1] / "models"
SEED = 42
START, LENGTH = 250.0, 375.0
END = START + LENGTH


@pytest.fixture(scope="module")
def catalog():
    model = read_bpmn(MODELS / "as_is.bpmn")
    return load_catalog(MODELS / "to_be.catalog.toml", model=model, params=load_parameters(MODELS / "as_is.params.toml", model))


@pytest.fixture(scope="module")
def replay(catalog):
    return build_replay(catalog, seed=SEED, start=START, length=LENGTH)


SCENARIOS = [("as_is", ()), ("to_be", ("C1", "C2", "C3", "C4"))]


def _scenario(replay, scenario_id):
    return next(s for s in replay["scenarios"] if s["id"] == scenario_id)


def _row_tuples(rows):
    return {(r["case"], r["activity"], r["lane"], r["ready"], r["start"], r["end"]) for r in rows}


@pytest.mark.parametrize(("scenario_id", "changes"), SCENARIOS)
def test_rows_are_the_simulators_task_rows_that_overlap_the_window(catalog, replay, scenario_id, changes):
    model, params = catalog.resolve(changes)
    log = simulate(model, params, n_cases=300, seed=SEED)  # cases arriving after the warm-up
    tasks = log[(log.element_type == "task") & (log.ready_time < END) & (log.end_time > START)].round(2)
    expected = {(int(r.case_id), r.activity_id, r.lane_id, r.ready_time, r.start_time, r.end_time) for r in tasks.itertuples()}

    rows = _scenario(replay, scenario_id)["rows"]
    after_warm_up = [r for r in rows if r["case"] >= log.case_id.min()]

    assert _row_tuples(after_warm_up) == expected


def test_both_scenarios_have_the_same_case_arrivals(replay):
    arrivals = [{c["id"]: c["arrival"] for c in s["cases"] if c["arrival"] >= START} for s in replay["scenarios"]]
    assert arrivals[0] == arrivals[1]
    assert len(arrivals[0]) > 50  # about 0.234 arrivals a day over 375 days


@pytest.mark.parametrize(("scenario_id", "changes"), SCENARIOS)
def test_a_case_has_a_cycle_time_only_if_it_ends_inside_the_window(catalog, replay, scenario_id, changes):
    model, params = catalog.resolve(changes)
    log = simulate(model, params, n_cases=300, seed=SEED)
    arrival = log.groupby("case_id").ready_time.min()
    ends = case_ends(log, params.cycle_time_end)  # go-live, or the end event of a rejected request

    cases = {c["id"]: c for c in _scenario(replay, scenario_id)["cases"]}
    for case_id in arrival.index[arrival < END]:
        case = cases[case_id]
        assert case["arrival"] == round(arrival[case_id], 2)
        if ends[case_id] < END:
            assert case["cycle_time"] == pytest.approx(ends[case_id] - arrival[case_id], abs=0.01)
        else:
            assert case["cycle_time"] is None
    assert any(c["cycle_time"] is not None for c in cases.values())
    assert any(c["cycle_time"] is None for c in cases.values())


def test_every_row_belongs_to_a_listed_case_and_overlaps_the_window(replay):
    for scenario in replay["scenarios"]:
        case_ids = {c["id"] for c in scenario["cases"]}
        assert scenario["rows"]
        for row in scenario["rows"]:
            assert row["case"] in case_ids
            assert row["ready"] <= row["start"] <= row["end"]
            assert row["ready"] <= END and row["end"] >= START  # inclusive: times are rounded to 2 decimals


def test_the_replay_names_its_run_window_and_scenarios(replay):
    assert replay["seed"] == SEED
    assert replay["window"] == {"start": START, "end": END}
    assert replay["warm_up"] == 250
    assert replay["time_unit"] == "working days"
    assert replay["cycle_time_ends_at"] == "Task_StartOperation"
    assert [(s["id"], s["changes"]) for s in replay["scenarios"]] == [("as_is", []), ("to_be", ["C1", "C2", "C3", "C4"])]
    assert all(s["name"] for s in replay["scenarios"])


@pytest.mark.parametrize(("scenario_id", "changes"), SCENARIOS)
def test_each_scenario_lists_its_models_lanes_and_tasks_for_the_page_layout(catalog, replay, scenario_id, changes):
    model, _ = catalog.resolve(changes)
    scenario = _scenario(replay, scenario_id)
    assert scenario["lanes"] == list(model.lanes)
    assert scenario["tasks"] == [n.id for n in model.nodes_of_type("task")]
    assert {r["activity"] for r in scenario["rows"]} <= set(scenario["tasks"])
    assert {r["lane"] for r in scenario["rows"]} <= set(scenario["lanes"])


def test_the_as_is_queue_at_qc_builds_up_and_the_to_be_one_does_not(replay):
    def qc_queue(scenario, start, end):
        """Average number of QC tasks waiting for a tester between start and end."""
        waits = [(r["ready"], r["start"]) for r in scenario["rows"] if r["lane"] == "Lane_QualityControl"]
        return sum(max(0.0, min(begin, end) - max(ready, start)) for ready, begin in waits) / (end - start)

    as_is, to_be = _scenario(replay, "as_is"), _scenario(replay, "to_be")
    assert qc_queue(as_is, START, START + 20) < 1  # about empty when the window opens
    assert qc_queue(as_is, START, END) > 4
    assert qc_queue(to_be, START, END) < qc_queue(as_is, START, END) / 4


@pytest.mark.parametrize(("scenario_id", "changes"), SCENARIOS)
def test_each_scenario_has_its_lane_capacities_and_baseline_rework_rates(catalog, replay, scenario_id, changes):
    model, params = catalog.resolve(changes)
    scenario = _scenario(replay, scenario_id)
    assert scenario["capacities"] == params.lane_capacities
    assert scenario["rework"] == rework_rates(simulate(model, params, n_cases=2_000, seed=SEED), model)


def test_the_as_is_rework_rates_are_the_reports_baseline(replay):
    results = json.loads((Path(__file__).parents[1] / "web" / "results.json").read_text())
    assert _scenario(replay, "as_is")["rework"] == results["baseline"]["rework"]
    to_be = {r["gateway_id"]: r["rate"] for r in _scenario(replay, "to_be")["rework"]}
    as_is = {r["gateway_id"]: r["rate"] for r in results["baseline"]["rework"]}
    assert to_be["Gateway_TestSplit"] < as_is["Gateway_TestSplit"]  # C3 lowers the defect rate


def test_the_written_file_reads_back_and_stays_small(replay, tmp_path):
    path = write_replay(replay, tmp_path / "demo" / "replay.json")
    assert json.loads(path.read_text()) == replay
    assert path.stat().st_size < 1_000_000
