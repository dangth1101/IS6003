"""Proposed default parameters for the as-is model and the synthetic log they give.

The ranges below are the targets stated at the top of models/as_is.params.toml.
"""

import json
import re
import time
from pathlib import Path

import pandas as pd
import pytest

from bpmopt.analysis import cycle_times
from bpmopt.bpmn import read_bpmn
from bpmopt.ml import cycle_time_task, ml_section, rework_tasks
from bpmopt.parameters import load_parameters
from bpmopt.planted import load_planted_effects
from bpmopt.results import build_results, export_results, validate_results
from bpmopt.simulation import simulate
from bpmopt.value_added import load_value_added

ROOT = Path(__file__).parents[1]
MODEL = ROOT / "models" / "as_is.bpmn"
PARAMETERS = ROOT / "models" / "as_is.params.toml"
PLANTED_EFFECTS = ROOT / "models" / "as_is_planted_effects.md"
PLANTED_DATA = ROOT / "models" / "as_is.planted_effects.toml"
VALUE_ADDED = ROOT / "models" / "as_is.value_added.toml"
N_CASES = 2_000
NEGATIVE_CONTROL = "requesting_unit"


@pytest.fixture(scope="module")
def model():
    return read_bpmn(MODEL)


@pytest.fixture(scope="module")
def params(model):
    return load_parameters(PARAMETERS, model=model)


@pytest.fixture(scope="module")
def run(model, params):
    started = time.perf_counter()
    log = simulate(model, params, n_cases=N_CASES, seed=42)
    return log, time.perf_counter() - started


@pytest.fixture(scope="module")
def log(run):
    return run[0]


def test_parameters_cover_every_task_xor_split_and_lane_of_the_model(model, params):
    splits = {n.id for n in model.nodes_of_type("exclusiveGateway") if len(model.outgoing(n.id)) > 1}

    assert set(params.task_durations) == {n.id for n in model.nodes_of_type("task")}
    assert set(params.branch_probabilities) == splits
    assert set(params.lane_capacities) == set(model.lanes)
    assert params.arrival_rate and params.warm_up > 0


def test_every_rationale_is_marked_as_a_proposed_default(params):
    not_marked = [entry for entry, text in params.rationales.items() if not text.startswith("Proposed default.")]
    assert not not_marked


def test_a_log_of_the_target_size_simulates_quickly(run):
    log, seconds = run

    assert log.case_id.nunique() == N_CASES
    assert seconds < 30
    # Warm-up cases are dropped, so the log starts after case 1.
    assert log.case_id.min() > 1


def test_mean_cycle_time_of_a_closed_project_is_six_to_ten_months(log):
    ct = cycle_times(log)
    closed = ct[log.groupby("case_id").activity_id.last() == "End_ProjectClosed"]

    assert 120 <= closed.mean() <= 200


def _counts(log: pd.DataFrame) -> pd.Series:
    return log.activity_id.value_counts()


def test_proposals_are_sent_back_or_rejected_at_the_stated_rates(log):
    n = _counts(log)
    outcome = log.groupby("case_id").activity_id.last()

    assert 0.15 <= n["Task_ReviseProposal"] / n["Task_ApproveProposal"] <= 0.25
    assert 0.07 <= (outcome == "End_ProposalRejected").mean() <= 0.13


def test_plans_tests_and_releases_loop_back_at_the_stated_rates(log):
    n = _counts(log)
    # Every plan decision after the first one of a case was a "changes requested".
    plan_back = (n["Task_ApprovePlan"] - n["Task_BuildApplication"]) / n["Task_ApprovePlan"]
    failed_rounds = n["Task_FixDefects"] / n["Task_RunAcceptanceTests"]
    failed_once = log[log.activity_id == "Task_FixDefects"].case_id.nunique() / n["Task_BuildApplication"]
    releases_rejected = n["Task_RefineApplication"] / n["Task_ApproveRelease"]

    assert 0.15 <= plan_back <= 0.25
    assert 0.30 <= failed_rounds <= 0.45
    assert 0.30 <= failed_once <= 0.50
    assert 0.05 <= releases_rejected <= 0.12


def test_every_lane_is_busy_but_below_capacity_and_qc_is_the_bottleneck(log, params):
    """Utilisation rho = lambda / (c x mu) = arrival rate x work per case / capacity (Eq. 7.8 p.270, p.276).

    The book (p.276): above 100% the queue grows forever, and close to 100% it is unstable in practice.
    """
    tasks = log[log.element_type == "task"]
    work_per_case = (tasks.end_time - tasks.start_time).groupby(tasks.lane_id).sum() / log.case_id.nunique()
    rho = params.arrival_rate * work_per_case / pd.Series(params.lane_capacities)

    assert rho.between(0.7, 0.95).all(), rho.round(3).to_dict()
    assert rho.idxmax() == "Lane_QualityControl"


def test_waiting_is_a_real_but_minor_part_of_the_cycle_time(log):
    tasks = log[log.element_type == "task"]
    waiting = (tasks.start_time - tasks.ready_time).sum()

    assert 0.10 <= waiting / cycle_times(log).sum() <= 0.40


@pytest.fixture(scope="module")
def planted(params):
    return load_planted_effects(PLANTED_DATA, params)


def test_the_planted_effects_doc_lists_exactly_the_effects_in_the_data_file(planted):
    # load_planted_effects already checks the data file against the parameters, both ways.
    rows = [line for line in PLANTED_EFFECTS.read_text(encoding="utf-8").splitlines() if re.match(r"\| \d+ \|", line)]
    in_doc = [tuple(cell.strip().strip("`") for cell in row.split("|")[2:5]) for row in rows]

    assert sorted(in_doc) == sorted(planted.effects)


def test_the_negative_control_has_no_effect_and_is_listed_as_such(planted):
    assert planted.negative_control == NEGATIVE_CONTROL
    text = PLANTED_EFFECTS.read_text(encoding="utf-8")
    assert re.search(rf"`{NEGATIVE_CONTROL}`.*negative control", text, re.IGNORECASE)


def test_the_ml_should_find_every_planted_attribute_in_the_cycle_time_and_each_gateways_own_in_its_rework(model, planted):
    assert planted.expected_drivers(model) == {
        "cycle_time": ["complexity", "integrations", "team_workload", "security_level", "project_type"],
        "rework_Gateway_ProposalSplit": [],
        "rework_Gateway_PlanSplit": ["project_type"],
        "rework_Gateway_TestSplit": ["complexity", "integrations", "security_level"],
        "rework_Gateway_ReleaseSplit": ["project_type"],
    }


def test_a_planted_effects_file_missing_an_effect_of_the_parameters_is_rejected(tmp_path, params):
    text = PLANTED_DATA.read_text(encoding="utf-8")
    path = tmp_path / "planted.toml"
    path.write_text(text[: text.rindex("[[effects]]")])

    with pytest.raises(ValueError, match="Gateway_ReleaseSplit"):
        load_planted_effects(path, params)


def test_a_planted_effect_the_parameters_do_not_have_is_rejected(tmp_path, params):
    path = tmp_path / "planted.toml"
    path.write_text(
        PLANTED_DATA.read_text(encoding="utf-8")
        + '\n[[effects]]\nelement = "Task_DeployApplication"\nattribute = "complexity"\nkind = "duration"\n'
    )

    with pytest.raises(ValueError, match="Task_DeployApplication"):
        load_planted_effects(path, params)


def test_a_negative_control_with_an_effect_is_rejected(tmp_path, params):
    path = tmp_path / "planted.toml"
    path.write_text(PLANTED_DATA.read_text(encoding="utf-8").replace('"requesting_unit"', '"complexity"', 1))

    with pytest.raises(ValueError, match="negative control"):
        load_planted_effects(path, params)


def test_the_as_is_pipeline_writes_results_that_validate(tmp_path, model, params, log):
    # The notebook's path on the real model, parameters and seed.
    results = build_results(log=log, model=model, params=params, seed=42)
    results["value_added"] = load_value_added(VALUE_ADDED, model)
    results["ml"] = ml_section([cycle_time_task(log, seed=42), *rework_tasks(log, model, seed=42)])

    path = export_results(results, tmp_path, models={"as_is": MODEL})

    exported = json.loads(path.read_text())
    validate_results(exported)
    assert exported["models"]["as_is"]["lint"] == []
    assert exported["meta"]["case_count"] == N_CASES
    rework_ids = {f"rework_{r['gateway_id']}" for r in exported["baseline"]["rework"]}
    assert {t["id"] for t in exported["ml"]["tasks"]} == {"cycle_time"} | rework_ids
