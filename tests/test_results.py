import json
import re
from pathlib import Path

import jsonschema
import pandas as pd
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


def test_assumptions_table_lists_every_parameter_with_its_rationale(tmp_path, simulate_fixture, fixtures_dir):
    log = simulate_fixture("rework_with_activity", n_cases=10, seed=3, params="rework_with_activity.logistic")
    params = load_parameters(fixtures_dir / "rework_with_activity.logistic.params.toml")
    results = build_results(log=log, params=params, seed=3)
    path = export_results(results, tmp_path, models={"as_is": fixtures_dir / "rework_with_activity.bpmn"})

    assumptions = json.loads(path.read_text())["assumptions"]
    assert assumptions == [
        {"parameter": "attributes.complexity.distribution", "value": "choice(1: 0.4, 2: 0.4, 3: 0.2)", "rationale": "Fixture value."},
        {"parameter": "attributes.project_type.distribution", "value": "choice(web: 0.7, mobile: 0.3)", "rationale": "Fixture value."},
        {"parameter": "tasks.Task_TestBuild.duration", "value": 4.0, "rationale": "Fixture value."},
        {"parameter": "tasks.Task_FixDefects.duration", "value": 2.0, "rationale": "Fixture value."},
        {
            "parameter": "gateways.Gateway_LoopSplit.branches",
            "value": "Flow_Passed: rest, Flow_Failed: logistic(-2 + 1 × complexity + 1.5 × [project_type = mobile])",
            "rationale": "Fixture value.",
        },
    ]


def test_assumptions_show_arrivals_warm_up_lanes_and_triangular_durations(fixtures_dir, tmp_path):
    path = tmp_path / "all.params.toml"
    path.write_text(
        'version = "x"\n'
        '[arrivals]\nrate = 0.25\nrationale = "About one request a week."\n'
        '[warm_up]\nlength = 100\nrationale = "Long enough to fill the queues."\n'
        '[attributes.workload]\ndistribution = { triangular = [0.2, 0.6, 1.0] }\nrationale = "Share of the team busy."\n'
        '[attributes.integrations]\ndistribution = { poisson = 1.5 }\nrationale = "Most apps call one or two systems."\n'
        '[lanes.Lane_Dev]\ncapacity = 3\nrationale = "Three developers."\n'
        '[tasks.Task_BuildApp]\nduration = { triangular = [10, 20, 45] }\nrationale = "Scales with scope."\n'
    )
    params = load_parameters(path)
    log = pd.DataFrame({"case_id": [1], "ready_time": [0.0], "end_time": [1.0]})

    rows = {row["parameter"]: row["value"] for row in build_results(log=log, params=params, seed=1)["assumptions"]}

    assert rows == {
        "arrivals.rate": 0.25,
        "warm_up.length": 100.0,
        "attributes.workload.distribution": "triangular(0.2, 0.6, 1)",
        "attributes.integrations.distribution": "poisson(1.5)",
        "lanes.Lane_Dev.capacity": 3,
        "tasks.Task_BuildApp.duration": "triangular(10, 20, 45)",
    }


def test_assumptions_spell_out_a_scaled_duration(fixtures_dir):
    params = load_parameters(fixtures_dir / "sequence.scaled.params.toml")
    log = pd.DataFrame({"case_id": [1], "ready_time": [0.0], "end_time": [1.0]})

    rows = {row["parameter"]: row["value"] for row in build_results(log=log, params=params, seed=1)["assumptions"]}

    assert rows["tasks.Task_BuildApp.duration"] == "4 × (1 + 0.5 × complexity + 1 × [project_type = mobile])"


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
