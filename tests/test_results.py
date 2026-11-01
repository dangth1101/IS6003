import json

import jsonschema
import pytest

from bpmopt.parameters import load_parameters
from bpmopt.results import build_results, export_results, validate_results


@pytest.fixture
def exported(tmp_path, simulate_fixture, fixtures_dir):
    log = simulate_fixture("sequence", n_cases=10, seed=3)
    params = load_parameters(fixtures_dir / "sequence.params.toml")
    results = build_results(log=log, params=params, seed=3)
    path = export_results(results, tmp_path, models={"as_is": fixtures_dir / "sequence.bpmn"})
    return json.loads(path.read_text())


def test_exported_results_validate_against_the_schema(exported):
    validate_results(exported)


def test_exported_results_carry_meta_and_baseline(exported):
    assert exported["meta"]["seed"] == 3
    assert exported["meta"]["case_count"] == 10
    assert exported["meta"]["parameter_version"] == "fixture-1"
    assert exported["baseline"]["time_unit"] == "working days"
    assert exported["baseline"]["cycle_time"]["mean"] == pytest.approx(10.5)


def test_export_copies_the_model_next_to_the_results(exported, tmp_path, fixtures_dir):
    copied = tmp_path / exported["models"]["as_is"]["bpmn"]
    assert copied.read_bytes() == (fixtures_dir / "sequence.bpmn").read_bytes()


def test_results_without_a_baseline_are_rejected(exported):
    del exported["baseline"]

    with pytest.raises(jsonschema.ValidationError):
        validate_results(exported)
