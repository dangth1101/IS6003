"""ML task A: cycle time from case-start attributes, with SHAP drivers (ticket 11).

The fixture plants one driver: only project_type changes how often a case
fails testing and loops back, so it should explain most of the cycle time.
"""

import json
from pathlib import Path

import pytest

from bpmopt.bpmn import read_bpmn
from bpmopt.ml import cycle_time_task, ml_section
from bpmopt.parameters import load_parameters
from bpmopt.results import build_results, export_results, validate_results
from bpmopt.simulation import simulate

FIXTURES = Path(__file__).parent / "fixtures"

ATTRIBUTES = {"complexity", "project_type", "integrations", "workload"}


# Module scope: one simulation and one fit shared by the tests below.
@pytest.fixture(scope="module")
def planted_log():
    model = read_bpmn(FIXTURES / "rework_with_activity.bpmn")
    params = load_parameters(FIXTURES / "rework_with_activity.ml.params.toml")
    return simulate(model, params, n_cases=1_000, seed=7)


@pytest.fixture(scope="module")
def task(planted_log):
    return cycle_time_task(planted_log, seed=7)


def test_planted_driver_ranks_first(task):
    drivers = [d["feature"] for d in task["drivers"]]

    assert drivers[0] == "project_type"
    # One entry per attribute, even when the model sees project_type as one column per label.
    assert sorted(drivers) == sorted(ATTRIBUTES)
    shap = [d["mean_abs_shap"] for d in task["drivers"]]
    assert shap == sorted(shap, reverse=True)


def test_each_model_is_reported_next_to_the_reference(task):
    metrics = {m["id"]: m["metrics"] for m in task["models"]}

    assert list(metrics) == ["reference", "linear", "gradient_boosting"]
    # Predicting the training mean explains nothing on later cases.
    assert metrics["reference"]["r2"] == pytest.approx(0, abs=0.05)
    # Both real models find the planted effect. R² stays well below 1, because how
    # many times a case loops back is luck even when its project type is known.
    for model in ("linear", "gradient_boosting"):
        assert metrics[model]["mae"] < 0.9 * metrics["reference"]["mae"]
        assert metrics[model]["r2"] > 0.1


def test_ml_section_validates_against_the_schema(tmp_path, planted_log, task, fixtures_dir):
    params = load_parameters(fixtures_dir / "rework_with_activity.ml.params.toml")
    results = build_results(log=planted_log, params=params, seed=7)
    results["ml"] = ml_section([task])

    path = export_results(results, tmp_path, models={"as_is": fixtures_dir / "rework_with_activity.bpmn"})

    exported = json.loads(path.read_text())
    validate_results(exported)
    assert exported["ml"]["split"] == {"method": "chronological", "train_share": 0.8}
    assert [t["id"] for t in exported["ml"]["tasks"]] == ["cycle_time"]
