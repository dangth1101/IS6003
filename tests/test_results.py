import json
import re
from pathlib import Path

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
    assert exported["meta"]["replications"] == 1
    assert exported["meta"]["warm_up"] == 0
    # Fixed durations 2 + 5.5 + 3: every case takes exactly 10.5 days.
    assert exported["baseline"]["cycle_time"] == pytest.approx({"mean": 10.5, "median": 10.5, "p90": 10.5})


def test_results_report_the_warm_up_from_the_parameter_file(simulate_fixture, fixtures_dir):
    log = simulate_fixture("single_task", n_cases=60, seed=1, params="single_task.warmup")
    params = load_parameters(fixtures_dir / "single_task.warmup.params.toml")

    results = build_results(log=log, params=params, seed=1)

    assert results["meta"]["warm_up"] == 50.0


def test_exported_results_carry_the_page_text(exported):
    assert exported["text"]["lang"] == "en"
    assert exported["text"]["sections"]["problem"]["paragraphs"]


def test_export_copies_the_model_next_to_the_results(exported, tmp_path, fixtures_dir):
    copied = tmp_path / exported["models"]["as_is"]["bpmn"]
    assert copied.read_bytes() == (fixtures_dir / "sequence.bpmn").read_bytes()


def test_results_without_a_baseline_are_rejected(exported):
    del exported["baseline"]

    with pytest.raises(jsonschema.ValidationError):
        validate_results(exported)


WEB = Path(__file__).parents[1] / "web"
FAKE_RESULTS = WEB / "fixtures/fake_results.json"


@pytest.fixture
def fake() -> dict:
    return json.loads(FAKE_RESULTS.read_text(encoding="utf-8"))


def test_fake_results_validate_against_the_schema(fake):
    validate_results(fake)


def test_the_committed_page_results_validate_against_the_schema():
    # Rerun the notebook after a schema change, or the page breaks on its default file.
    validate_results(json.loads((WEB / "results.json").read_text(encoding="utf-8")))


def test_fake_results_fill_every_section_of_the_spec(fake):
    # Spec, "Results contract", plus `text` for the page wording.
    spec_sections = {"meta", "assumptions", "models", "value_added", "baseline", "ml", "changes", "scenarios", "threats"}

    assert set(fake) == spec_sections | {"text"}
    assert set(fake["models"]) == {"as_is", "to_be"}


def test_scenarios_must_cover_every_combination_of_changes(fake):
    fake["scenarios"] = [s for s in fake["scenarios"] if sorted(s["changes"]) != ["C1", "C3"]]

    with pytest.raises(jsonschema.ValidationError, match="C1, C3"):
        validate_results(fake)


def test_scenarios_may_only_use_changes_from_the_catalog(fake):
    fake["scenarios"].append({**fake["scenarios"][0], "changes": ["C9"]})

    with pytest.raises(jsonschema.ValidationError, match="C9"):
        validate_results(fake)


def test_a_confidence_interval_must_contain_its_estimate(fake):
    fake["scenarios"][1]["saving"] = {"value": 5.0, "ci_low": 6.0, "ci_high": 7.0}

    with pytest.raises(jsonschema.ValidationError, match="interval"):
        validate_results(fake)


def test_a_generated_at_that_is_not_a_timestamp_is_rejected(fake):
    fake["meta"]["generated_at"] = "yesterday"

    with pytest.raises(jsonschema.ValidationError, match="date-time"):
        validate_results(fake)


def test_the_page_uses_exactly_the_labels_the_schema_requires():
    # All page wording comes from text.labels via t("key"). If the page used a key the
    # schema doesn't require, a valid results file could leave it blank on screen.
    page = (WEB / "index.html").read_text(encoding="utf-8")
    used = set(re.findall(r"""\bt\(["']([A-Za-z0-9_]+)["']""", page))
    schema = json.loads((Path(__file__).parents[1] / "src/bpmopt/schema/results.schema.json").read_text())

    assert used == set(schema["$defs"]["labels"]["required"])
