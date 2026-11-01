"""Value-added classification (book §6.1): one class per task, kept as data."""

import json
from pathlib import Path

import pytest

from bpmopt.bpmn import read_bpmn
from bpmopt.results import validate_results
from bpmopt.value_added import load_value_added

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
