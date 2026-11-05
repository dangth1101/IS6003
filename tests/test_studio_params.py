"""The studio's parameter panel, import and export, through the bpmopt.studio seam.

The page edits one entry at a time (set_parameter), imports a parameter file
(params_from_toml, then default_parameters) and exports one (params_to_toml).
"""

import tomllib
from pathlib import Path

import pytest

from bpmopt.bpmn import read_bpmn
from bpmopt.parameters import load_parameters, parse_parameters
from bpmopt.studio import default_parameters, fixed_branches, params_to_toml, set_parameter, simulate_summary

ROOT = Path(__file__).parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
AS_IS = ROOT / "models" / "as_is.bpmn"
AS_IS_PARAMS = ROOT / "models" / "as_is.params.toml"
PARAMETER_FILES = sorted([AS_IS_PARAMS, *FIXTURES.glob("*.params.toml")])


@pytest.mark.parametrize("path", PARAMETER_FILES, ids=lambda p: p.name)
def test_exported_parameters_read_back_to_the_same_tables(path):
    params = tomllib.loads(path.read_text())

    assert tomllib.loads(params_to_toml(params)) == params


def test_an_exported_parameter_file_loads_in_the_notebooks_load_parameters(tmp_path):
    # An imported model without a parameter file: every entry a studio default, then exported.
    xml = (FIXTURES / "proposal_rejected.bpmn").read_text()
    params = default_parameters(xml)["params"]
    (tmp_path / "model.bpmn").write_text(xml)
    (tmp_path / "model.params.toml").write_text(params_to_toml(params))

    loaded = load_parameters(tmp_path / "model.params.toml", read_bpmn(tmp_path / "model.bpmn"))

    assert loaded == parse_parameters(params)
    assert loaded.rationales["tasks.Task_BuildApp"].startswith("Studio default.")


def test_exported_bpmn_and_parameters_reimport_to_the_same_run():
    xml = (FIXTURES / "proposal_rejected.bpmn").read_text()
    params = default_parameters(xml)["params"]
    run = {"n_cases": 100, "seed": 9, "replications": 3}

    reimported = default_parameters(xml, tomllib.loads(params_to_toml(params)))

    assert reimported["defaults"] == default_parameters(xml)["defaults"]
    assert simulate_summary(xml, reimported["params"], **run) == simulate_summary(xml, params, **run)


def as_is_preset() -> tuple[str, dict]:
    return AS_IS.read_text(), tomllib.loads(AS_IS_PARAMS.read_text())


def test_an_edited_entry_gets_the_new_value_and_its_own_rationale():
    xml, params = as_is_preset()

    edited = set_parameter(xml, params, "tasks.Task_DraftPlan", {"duration": {"triangular": [3, 5, 9]}})

    entry = edited["params"]["tasks"]["Task_DraftPlan"]
    assert entry == {"duration": {"triangular": [3, 5, 9]}, "rationale": "Set in the studio."}
    assert {**edited["params"], "tasks": {**edited["params"]["tasks"], "Task_DraftPlan": params["tasks"]["Task_DraftPlan"]}} == params
    assert edited["defaults"] == [] and edited["dropped"] == []


def test_an_edited_default_is_no_longer_marked_as_a_default():
    xml = (FIXTURES / "proposal_rejected.bpmn").read_text()
    filled = default_parameters(xml)

    edited = set_parameter(xml, filled["params"], "lanes.Lane_Dev", {"capacity": 2})

    assert "lanes.Lane_Dev" in filled["defaults"]
    assert edited["defaults"] == [entry for entry in filled["defaults"] if entry != "lanes.Lane_Dev"]


def test_setting_the_arrival_rate_and_warm_up_of_a_model_without_them():
    xml = (FIXTURES / "sequence.bpmn").read_text()
    params = tomllib.loads((FIXTURES / "sequence.params.toml").read_text())
    assert "arrivals" not in params

    edited = set_parameter(xml, params, "arrivals", {"rate": 0.5})
    edited = set_parameter(xml, edited["params"], "warm_up", {"length": 20})

    assert parse_parameters(edited["params"]).arrival_rate == 0.5
    assert parse_parameters(edited["params"]).warm_up == 20


@pytest.mark.parametrize(
    ("entry", "fields", "message"),
    [
        ("tasks.Task_DraftPlan", {"duration": {"triangular": [5, 3, 9]}}, "Task_DraftPlan"),
        ("gateways.Gateway_ProposalSplit",
         {"branches": {"Flow_ProposalApproved": 0.5, "Flow_ProposalChangesRequested": 0.2, "Flow_ProposalRejected": 0.2}}, "sum to 1"),
        ("lanes.Lane_QualityControl", {"capacity": 0}, "at least 1"),
        ("arrivals", {"rate": -1}, "positive"),
        ("tasks.Task_Nowhere", {"duration": {"fixed": 1}}, "Task_Nowhere"),
    ],
)
def test_an_invalid_edit_is_refused_with_the_reason(entry, fields, message):
    xml, params = as_is_preset()

    with pytest.raises(ValueError, match=message):
        set_parameter(xml, params, entry, fields)


def mean_cycle_time(xml: str, params: dict) -> float:
    return simulate_summary(xml, params, n_cases=300, seed=4, replications=3)["cycle_time"]["mean"]["value"]


@pytest.mark.parametrize(
    ("entry", "fields", "direction"),
    [
        ("tasks.Task_BuildApplication", {"duration": {"triangular": [40, 60, 90]}}, +1),  # a longer task
        ("gateways.Gateway_ProposalSplit",  # more proposals sent back for changes
         {"branches": {"Flow_ProposalApproved": 0.47, "Flow_ProposalChangesRequested": 0.5, "Flow_ProposalRejected": 0.03}}, +1),
        ("lanes.Lane_QualityControl", {"capacity": 20}, -1),  # more testers, less waiting
    ],
)
def test_an_edit_moves_the_next_runs_cycle_time_in_the_expected_direction(entry, fields, direction):
    xml, params = as_is_preset()

    edited = set_parameter(xml, params, entry, fields)

    assert direction * (mean_cycle_time(xml, edited["params"]) - mean_cycle_time(xml, params)) > 0


@pytest.mark.parametrize(
    ("gateway_id", "logistic_flow", "low", "high"),
    [
        # The shares the as-is parameter file states for these logistic branches.
        ("Gateway_TestSplit", "Flow_DefectsFound", 0.28, 0.40),  # "about a third of test rounds find defects"
        ("Gateway_PlanSplit", "Flow_PlanChangesRequested", 0.15, 0.21),  # "about 18% overall"
    ],
)
def test_reset_to_fixed_replaces_a_logistic_branch_with_its_share_over_the_case_attributes(gateway_id, logistic_flow, low, high):
    xml, params = as_is_preset()

    branches = fixed_branches(params, gateway_id)

    assert low <= branches[logistic_flow] <= high
    rest = next(flow for flow in branches if flow != logistic_flow)
    assert branches[rest] == "rest"
    reset = set_parameter(xml, params, f"gateways.{gateway_id}", {"branches": branches})
    assert reset["params"]["gateways"][gateway_id]["branches"] == branches


def test_reset_to_fixed_keeps_fixed_branches_as_they_are():
    _, params = as_is_preset()

    assert fixed_branches(params, "Gateway_ProposalSplit") == params["gateways"]["Gateway_ProposalSplit"]["branches"]
