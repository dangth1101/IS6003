"""Proposed default parameters for the as-is model and the synthetic log they give (ticket 10).

The ranges below are the targets stated at the top of models/as_is.params.toml.
"""

import re
import time
from pathlib import Path

import pandas as pd
import pytest

from bpmopt.analysis import cycle_times
from bpmopt.bpmn import read_bpmn
from bpmopt.parameters import Logistic, ScaledDuration, load_parameters
from bpmopt.simulation import simulate

ROOT = Path(__file__).parents[1]
MODEL = ROOT / "models" / "as_is.bpmn"
PARAMETERS = ROOT / "models" / "as_is.params.toml"
PLANTED_EFFECTS = ROOT / "models" / "as_is_planted_effects.md"
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


def _planted(params) -> set[tuple[str, str]]:
    """(element ID, attribute) for every attribute term in the parameters."""
    terms = {(task_id, name) for task_id, d in params.task_durations.items() if isinstance(d, ScaledDuration) for name in d.coefficients}
    for gateway_id, branches in params.branch_probabilities.items():
        for p in branches.flows.values():
            if isinstance(p, Logistic):
                terms |= {(gateway_id, name) for name in p.coefficients}
    return terms


def test_every_planted_effect_is_listed_in_the_planted_effects_doc(params):
    rows = [line for line in PLANTED_EFFECTS.read_text(encoding="utf-8").splitlines() if line.startswith("|")]

    def listed(element_id: str, attribute: str) -> bool:
        return any(re.search(rf"`{element_id}`", row) and re.search(rf"`{attribute}`", row) for row in rows)

    missing = [term for term in _planted(params) if not listed(*term)]
    assert not missing
    # And nothing in the doc that the parameters don't plant.
    for row in rows:
        ids = re.findall(r"`((?:Task|Gateway)_\w+)`", row)
        names = [n for n in re.findall(r"`(\w+)`", row) if n in params.attributes]
        assert all((i, n) in _planted(params) for i in ids for n in names), row


def test_the_negative_control_has_no_effect_and_is_listed_as_such(params):
    assert NEGATIVE_CONTROL in params.attributes
    assert all(name != NEGATIVE_CONTROL for _, name in _planted(params))
    text = PLANTED_EFFECTS.read_text(encoding="utf-8")
    assert re.search(rf"`{NEGATIVE_CONTROL}`.*negative control", text, re.IGNORECASE)
