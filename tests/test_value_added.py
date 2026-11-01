"""Value-added classification (book §6.1): one class per task, kept as data."""

import json
from pathlib import Path

import pytest

from bpmopt.bpmn import read_bpmn
from bpmopt.parameters import load_parameters
from bpmopt.results import validate_results
from bpmopt.simulation import simulate
from bpmopt.value_added import load_value_added, time_per_class

ROOT = Path(__file__).parents[1]
MODEL = ROOT / "models" / "as_is.bpmn"
CLASSIFICATION = ROOT / "models" / "as_is.value_added.toml"
FAKE_RESULTS = ROOT / "web" / "fixtures" / "fake_results.json"


def test_every_task_of_the_as_is_model_has_exactly_one_classification():
    model = read_bpmn(MODEL)

    value_added = load_value_added(CLASSIFICATION, model)

    tasks = {n.id for n in model.nodes_of_type("task")}
    assert set(value_added) == tasks
    for entry in value_added.values():
        assert entry["class"] in {"VA", "BVA", "NVA"}
        assert entry["reason"].strip()


def test_value_added_section_validates_against_the_schema():
    results = json.loads(FAKE_RESULTS.read_text(encoding="utf-8"))
    results["value_added"] = load_value_added(CLASSIFICATION, read_bpmn(MODEL))

    validate_results(results)


def test_time_per_class_sums_the_task_time_of_each_class_per_case(tmp_path, fixtures_dir, simulate_fixture):
    # Fixed durations: Write specification 2, Build application 5.5, Test application 3 days.
    path = tmp_path / "sequence.value_added.toml"
    path.write_text(
        '[Task_WriteSpec]\nclass = "VA"\nreason = "r"\n'
        '[Task_BuildApp]\nclass = "VA"\nreason = "r"\n'
        '[Task_TestApp]\nclass = "NVA"\nreason = "r"\n'
    )
    value_added = load_value_added(path, read_bpmn(fixtures_dir / "sequence.bpmn"))

    table = time_per_class(simulate_fixture("sequence", n_cases=10), value_added)

    assert list(table.index) == ["VA", "BVA", "NVA"]
    assert table.tasks.tolist() == [2, 0, 1]
    assert table.days_per_case.tolist() == pytest.approx([7.5, 0.0, 3.0])
    assert table.share.tolist() == pytest.approx([7.5 / 10.5, 0.0, 3 / 10.5])


def test_time_per_class_counts_every_run_of_a_reworked_task(tmp_path, fixtures_dir):
    # Test build takes 4 days and fails a quarter of the time; each failure adds Fix defects
    # (2 days) and another test round. Per case: 4 / 0.75 days of testing, 2 x 0.25 / 0.75 of fixing.
    model = read_bpmn(fixtures_dir / "rework_with_activity.bpmn")
    path = tmp_path / "rework.value_added.toml"
    path.write_text('[Task_TestBuild]\nclass = "BVA"\nreason = "r"\n[Task_FixDefects]\nclass = "NVA"\nreason = "r"\n')
    log = simulate(model, load_parameters(fixtures_dir / "rework_with_activity.params.toml"), n_cases=20_000, seed=1)

    table = time_per_class(log, load_value_added(path, model))

    assert table.days_per_case["BVA"] == pytest.approx(4 / 0.75, rel=0.02)
    assert table.days_per_case["NVA"] == pytest.approx(0.5 / 0.75, rel=0.05)


def test_a_task_without_a_classification_is_rejected(tmp_path, fixtures_dir):
    path = tmp_path / "partial.value_added.toml"
    path.write_text('[Task_WriteSpec]\nclass = "VA"\nreason = "Does the work."\n')

    with pytest.raises(ValueError, match="Task_BuildApp"):
        load_value_added(path, read_bpmn(fixtures_dir / "sequence.bpmn"))


def test_an_id_that_is_not_a_task_of_the_model_is_rejected(tmp_path, fixtures_dir):
    model = read_bpmn(fixtures_dir / "sequence.bpmn")
    entries = "".join(f'[{t.id}]\nclass = "VA"\nreason = "Does the work."\n' for t in model.nodes_of_type("task"))
    path = tmp_path / "extra.value_added.toml"
    path.write_text(entries + '[Task_Gone]\nclass = "NVA"\nreason = "Removed."\n')

    with pytest.raises(ValueError, match="Task_Gone"):
        load_value_added(path, model)
