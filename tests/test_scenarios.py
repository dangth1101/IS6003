"""Change catalog, scenarios and the scenario runner (ticket 13).

Fixture catalog: tests/fixtures/sequence.catalog.toml on sequence.bpmn.
C1 takes 2 days off Build application (parameter-only), C2 removes Write
specification (structural, another model file), C3 adds a developer
(parameter-only, a lane capacity).
"""

import pandas as pd
import pytest

from bpmopt.analysis import mean_cycle_time
from bpmopt.bpmn import read_bpmn
from bpmopt.parameters import load_parameters
from bpmopt.results import build_results, validate_results
from bpmopt.scenarios import ablation, load_catalog, replication_seeds, run_scenarios, t_quantile_975
from bpmopt.simulation import simulate


@pytest.fixture
def load(fixtures_dir):
    """Load the fixture catalog against sequence.bpmn and the given parameter file."""

    def run(params: str, catalog: str = "sequence.catalog.toml"):
        model = read_bpmn(fixtures_dir / "sequence.bpmn")
        return load_catalog(fixtures_dir / catalog, model=model, params=load_parameters(fixtures_dir / f"{params}.params.toml"))

    return run


def _by_changes(scenarios):
    return {frozenset(s["changes"]): s for s in scenarios}


def test_a_change_that_removes_a_fixed_amount_of_work_saves_exactly_that_much(load):
    # C1 shifts the triangular duration of Build application down by 2 days. With
    # unlimited capacity and common random numbers every case draws the same
    # uniform for the task in both scenarios, so every case is exactly 2 days faster.
    catalog = load("sequence.triangular")

    scenarios = _by_changes(run_scenarios(catalog, n_cases=20, replications=3, seed=1))

    saving = scenarios[frozenset({"C1"})]["saving"]
    assert saving["value"] == pytest.approx(2.0)
    assert saving["ci_low"] == pytest.approx(2.0)
    assert saving["ci_high"] == pytest.approx(2.0)


def test_the_ci_uses_the_t_quantile_from_the_usual_table():
    # Two-sided 95% t values from any statistics table.
    assert [round(t_quantile_975(df), 3) for df in (1, 2, 5, 10, 29, 100)] == [12.706, 4.303, 2.571, 2.228, 2.045, 1.984]


def test_the_empty_scenario_reproduces_the_as_is_run_exactly(load, fixtures_dir):
    catalog = load("sequence.scenarios")
    seeds = replication_seeds(5, 3)

    scenarios = _by_changes(run_scenarios(catalog, n_cases=30, replications=3, seed=5))

    model = read_bpmn(fixtures_dir / "sequence.bpmn")
    params = load_parameters(fixtures_dir / "sequence.scenarios.params.toml")
    as_is_means = [mean_cycle_time(simulate(model, params, n_cases=30, seed=s)) for s in seeds]
    as_is = scenarios[frozenset()]
    assert as_is["cycle_time"]["mean"]["value"] == pytest.approx(sum(as_is_means) / 3, abs=1e-12)
    assert as_is["saving"] == {"value": 0.0, "ci_low": 0.0, "ci_high": 0.0}
    # Queues make the replications differ, so the CI has some width.
    assert as_is["cycle_time"]["mean"]["ci_low"] < as_is["cycle_time"]["mean"]["value"]


def test_every_combination_of_changes_is_simulated_and_the_results_validate(load):
    catalog = load("sequence.scenarios")
    model, params = catalog.resolve([])
    log = simulate(model, params, n_cases=30, seed=5)

    scenarios = run_scenarios(catalog, n_cases=30, replications=3, seed=5)

    assert len(scenarios) == 2**3
    assert {frozenset(s["changes"]) for s in scenarios} == {
        frozenset(c) for c in [(), ("C1",), ("C2",), ("C3",), ("C1", "C2"), ("C1", "C3"), ("C2", "C3"), ("C1", "C2", "C3")]
    }
    results = build_results(log=log, model=model, params=params, seed=5)
    results |= {"models": {"as_is": {"bpmn": "models/as_is.bpmn"}}, "changes": catalog.entries(), "scenarios": scenarios}
    validate_results(results)


def _durations(log):
    tasks = log[log.element_type == "task"]
    return (tasks.end_time - tasks.start_time).set_axis(pd.MultiIndex.from_frame(tasks[["case_id", "activity_id"]]))


def test_removing_a_task_leaves_every_other_draw_unchanged(load):
    # Common random numbers: C2 removes Write specification, the first task of
    # every case. The other tasks of every case must still draw the same durations,
    # and cases must arrive at the same times, or the saving would mix the design
    # effect with noise.
    catalog = load("sequence.scenarios")

    as_is = simulate(*catalog.resolve([]), n_cases=30, seed=9)
    without_spec = simulate(*catalog.resolve(["C2"]), n_cases=30, seed=9)

    assert "Task_WriteSpec" not in set(without_spec.activity_id)
    kept = _durations(as_is).drop("Task_WriteSpec", level="activity_id")
    pd.testing.assert_series_equal(_durations(without_spec), kept)
    arrivals = lambda log: log[log.element_type == "startEvent"].set_index("case_id").start_time
    pd.testing.assert_series_equal(arrivals(without_spec), arrivals(as_is))


def test_changing_one_task_leaves_the_draws_of_other_tasks_and_cases_unchanged(load):
    # C1 changes Build application only. Queues shift start times, but every
    # other task keeps its duration in every case.
    catalog = load("sequence.scenarios")

    as_is = simulate(*catalog.resolve([]), n_cases=30, seed=9)
    faster_build = simulate(*catalog.resolve(["C1"]), n_cases=30, seed=9)

    other = lambda log: _durations(log).drop("Task_BuildApp", level="activity_id")
    pd.testing.assert_series_equal(other(faster_build), other(as_is))
    assert (_durations(faster_build).xs("Task_BuildApp", level="activity_id") < _durations(as_is).xs("Task_BuildApp", level="activity_id")).all()


def test_a_structural_change_runs_on_its_own_model_and_saves_the_removed_work(load):
    # C2 runs on sequence_without_spec.bpmn. With unlimited capacity each case is
    # faster by exactly its Write specification time, triangular(1, 2, 3), mean 2.
    catalog = load("sequence.triangular")

    model, params = catalog.resolve(["C2"])
    scenarios = _by_changes(run_scenarios(catalog, n_cases=40, replications=5, seed=3))

    assert model.process_id == "Process_SequenceWithoutSpec"
    assert "Task_WriteSpec" not in params.task_durations
    saving = scenarios[frozenset({"C2"})]["saving"]
    assert saving["ci_low"] < 2.0 < saving["ci_high"]
    assert saving["ci_high"] - saving["ci_low"] < 0.3


def test_ablation_views_come_straight_from_the_factorial_results(load):
    catalog = load("sequence.scenarios")
    scenarios = run_scenarios(catalog, n_cases=30, replications=3, seed=5)
    by_changes = _by_changes(scenarios)
    full = by_changes[frozenset({"C1", "C2", "C3"})]["saving"]["value"]

    rows = {row["change"]: row for row in ablation(scenarios)}

    assert list(rows) == ["C1", "C2", "C3"]
    for change_id, row in rows.items():
        assert row["alone"] == by_changes[frozenset({change_id})]["saving"]
        without = by_changes[frozenset({"C1", "C2", "C3"} - {change_id})]["saving"]["value"]
        assert row["full_minus"] == pytest.approx(full - without)
    # Every change shortens the cycle time here, on its own and in the full design.
    assert all(row["alone"]["value"] > 0 and row["full_minus"] > 0 for row in rows.values())


# Small catalogs written per test. Descriptive fields are placeholders.
def _change(change_id: str, body: str = "") -> str:
    return f"""
[changes.{change_id}]
title = "Change {change_id}"
driver = "A driver."
heuristic = {{ name = "Activity elimination", ref = "Appendix A.2" }}
expected_effect = "Faster."
trade_off = {{ time = "better", cost = "neutral", quality = "neutral", flexibility = "neutral", note = "" }}
{body}
"""


FASTER_BUILD = """
[changes.C1.overrides.tasks.Task_BuildApp]
duration = { triangular = [1.0, 3.0, 8.0] }
rationale = "Shifted down by 2 days."
"""


@pytest.fixture
def write_catalog(tmp_path, fixtures_dir, load):
    """Write a catalog next to a copy of the structural fixture model and load it."""

    def run(text: str, params: str = "sequence.scenarios"):
        (tmp_path / "without_spec.bpmn").write_bytes((fixtures_dir / "sequence_without_spec.bpmn").read_bytes())
        (tmp_path / "catalog.toml").write_text('version = "test"\n' + text)
        return load(params, catalog=tmp_path / "catalog.toml")

    return run


def test_with_no_interaction_the_ablation_views_agree(write_catalog):
    # With unlimited capacity C1 and C2 add up case by case, so each change saves
    # as much alone as it adds to the full design.
    catalog = write_catalog(_change("C1", FASTER_BUILD) + _change("C2") + '[models]\nC2 = "without_spec.bpmn"\n', params="sequence.triangular")

    rows = ablation(run_scenarios(catalog, n_cases=20, replications=3, seed=2))

    for row in rows:
        assert row["full_minus"] == pytest.approx(row["alone"]["value"])


def test_two_structural_changes_need_a_model_for_their_combination(write_catalog):
    text = _change("C1") + _change("C2") + '[models]\nC1 = "without_spec.bpmn"\nC2 = "without_spec.bpmn"\n'

    with pytest.raises(ValueError, match=r"C1\+C2"):
        write_catalog(text)


def test_an_override_needs_a_rationale(write_catalog):
    body = "[changes.C1.overrides.tasks.Task_BuildApp]\nduration = { fixed = 1.0 }\n"

    with pytest.raises(ValueError, match="rationale"):
        write_catalog(_change("C1", body))


def test_an_override_for_a_task_no_model_has_is_an_error(write_catalog):
    body = '[changes.C1.overrides.tasks.Task_BiuldApp]\nduration = { fixed = 1.0 }\nrationale = "Typo."\n'

    with pytest.raises(ValueError, match="Task_BiuldApp"):
        write_catalog(_change("C1", body))


def test_two_changes_can_not_override_the_same_entry(write_catalog):
    with pytest.raises(ValueError, match="tasks.Task_BuildApp"):
        write_catalog(_change("C1", FASTER_BUILD) + _change("C2", FASTER_BUILD.replace("C1", "C2")))


def test_a_trade_off_must_say_better_worse_or_neutral(write_catalog):
    text = _change("C1").replace('cost = "neutral"', 'cost = "higher"')

    with pytest.raises(ValueError, match=r"changes\.C1\.trade_off\.cost: 'higher'"):
        write_catalog(text)


def test_a_change_can_not_alter_the_demand(write_catalog):
    # Arrivals, attributes and the warm-up stay the same in every scenario, or the
    # comparison would no longer be about the design.
    body = '[changes.C1.overrides.arrivals]\nrate = 0.1\nrationale = "Fewer requests."\n'

    with pytest.raises(ValueError, match="arrivals"):
        write_catalog(_change("C1", body))


def test_a_change_needs_every_catalog_field(write_catalog):
    text = _change("C1").replace('expected_effect = "Faster."\n', "")

    with pytest.raises(ValueError, match="expected_effect"):
        write_catalog(text)


def test_a_gateway_override_on_an_xor_join_is_an_error(tmp_path, fixtures_dir):
    # Only XOR-splits have branches. An override on a join would be dropped without a word.
    body = (
        "[changes.C1.overrides.gateways.Gateway_LoopJoin]\n"
        "branches = { Flow_Passed = 0.9, Flow_Failed = 0.1 }\n"
        'rationale = "Wrong gateway."\n'
    )
    (tmp_path / "catalog.toml").write_text('version = "test"\n' + _change("C1", body))
    model = read_bpmn(fixtures_dir / "rework_with_activity.bpmn")
    params = load_parameters(fixtures_dir / "rework_with_activity.params.toml")

    with pytest.raises(ValueError, match="Gateway_LoopJoin"):
        load_catalog(tmp_path / "catalog.toml", model=model, params=params)
