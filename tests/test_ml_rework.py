"""ML task B: rework per gateway from case-start attributes, with SHAP drivers (ticket 12).

The fixture has two rework gateways. Only complexity drives the test loop; the
proposal loop is a fixed 25%, and 15% of cases are rejected before testing.
"""

import json
from pathlib import Path

import pytest

from bpmopt.bpmn import read_bpmn
from bpmopt.ml import cycle_time_task, ml_section, rework_tasks
from bpmopt.parameters import load_parameters
from bpmopt.results import build_results, export_results, validate_results
from bpmopt.simulation import simulate

FIXTURES = Path(__file__).parent / "fixtures"

ATTRIBUTES = {"complexity", "project_type", "integrations", "workload"}


@pytest.fixture(scope="module")
def model():
    return read_bpmn(FIXTURES / "proposal_rejected.bpmn")


# Module scope: one simulation and one fit shared by the tests below.
@pytest.fixture(scope="module")
def planted_log(model):
    params = load_parameters(FIXTURES / "proposal_rejected.ml.params.toml")
    return simulate(model, params, n_cases=3_000, seed=7)


@pytest.fixture(scope="module")
def tasks(planted_log, model):
    return {task["gateway_id"]: task for task in rework_tasks(planted_log, model, seed=7)}


def test_one_classifier_per_rework_gateway(tasks):
    assert set(tasks) == {"Gateway_TestSplit", "Gateway_ReviewSplit"}
    for gateway_id, task in tasks.items():
        assert task["id"] == f"rework_{gateway_id}"
        assert task["kind"] == "classification"


def test_planted_driver_ranks_first_for_its_gateway(tasks):
    drivers = [d["feature"] for d in tasks["Gateway_TestSplit"]["drivers"]]

    assert drivers[0] == "complexity"
    assert sorted(drivers) == sorted(ATTRIBUTES)
    shap = [d["mean_abs_shap"] for d in tasks["Gateway_TestSplit"]["drivers"]]
    assert shap == sorted(shap, reverse=True)


def test_each_model_is_reported_next_to_the_reference(tasks):
    metrics = {m["id"]: m["metrics"] for m in tasks["Gateway_TestSplit"]["models"]}

    assert list(metrics) == ["reference", "linear", "gradient_boosting"]
    # Always guessing "no rework" (the majority) ranks nothing and finds no reworked case.
    assert metrics["reference"] == {"roc_auc": 0.5, "f1": 0.0}
    for model in ("linear", "gradient_boosting"):
        assert metrics[model]["roc_auc"] > 0.65


def test_minority_class_is_still_predicted(tasks):
    # About 1 in 9 cases that reach testing fail it, and no group fails more often than not,
    # so an unweighted model never predicts rework (F1 0). Balanced class weights fix that.
    metrics = {m["id"]: m["metrics"] for m in tasks["Gateway_TestSplit"]["models"]}

    for model in ("linear", "gradient_boosting"):
        assert metrics[model]["f1"] > 0.2


def test_a_gateway_no_attribute_drives_scores_near_chance(tasks):
    # The proposal loop is a fixed 25%: nothing known at case start predicts it.
    metrics = {m["id"]: m["metrics"] for m in tasks["Gateway_ReviewSplit"]["models"]}

    for model in ("linear", "gradient_boosting"):
        assert metrics[model]["roc_auc"] == pytest.approx(0.5, abs=0.1)


def test_rework_and_cycle_time_sit_side_by_side_in_the_ml_section(tmp_path, planted_log, model, tasks):
    params = load_parameters(FIXTURES / "proposal_rejected.ml.params.toml")
    results = build_results(log=planted_log, params=params, model=model, seed=7)
    results["ml"] = ml_section([cycle_time_task(planted_log, seed=7), *tasks.values()])

    path = export_results(results, tmp_path, models={"as_is": FIXTURES / "proposal_rejected.bpmn"})

    exported = json.loads(path.read_text())
    validate_results(exported)
    assert exported["ml"]["split"] == {"method": "chronological", "train_share": 0.8}
    assert [t["id"] for t in exported["ml"]["tasks"]] == [
        "cycle_time",
        "rework_Gateway_TestSplit",
        "rework_Gateway_ReviewSplit",
    ]


def test_a_gateway_that_never_loops_back_is_refused_with_a_clear_message(tmp_path, model):
    text = (FIXTURES / "proposal_rejected.ml.params.toml").read_text()
    never_fails = text.replace(
        "Flow_Failed = { logistic = { intercept = -4.5, complexity = 1.2 } }", "Flow_Failed = 0.0"
    ).replace('Flow_Passed = "rest"', "Flow_Passed = 1.0")
    (tmp_path / "never_fails.toml").write_text(never_fails)
    log = simulate(model, load_parameters(tmp_path / "never_fails.toml"), n_cases=200, seed=1)

    with pytest.raises(ValueError, match="Gateway_TestSplit"):
        rework_tasks(log, model, seed=1)
