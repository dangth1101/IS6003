"""The studio's suggestions panel, through the bpmopt.studio seam.

The panel asks suggestions(xml, params) what the current design is (which
catalog changes it carries, and whether its parameters are still the
catalog's), applies a change set with apply_suggestion, and highlights what
a step changed with diff_designs.
"""

import json
import tomllib
from itertools import combinations
from pathlib import Path

import pytest

from bpmopt.bpmn import read_bpmn
from bpmopt.parameters import load_parameters
from bpmopt.scenarios import load_catalog
from bpmopt.studio import apply_suggestion, default_parameters, diff_designs, set_parameter, suggestions

ROOT = Path(__file__).parents[1]
MODELS = ROOT / "models"
AS_IS = MODELS / "as_is.bpmn"
AS_IS_PARAMS = MODELS / "as_is.params.toml"
PRESET_FILES = ["as_is.bpmn", "as_is.params.toml", "to_be.catalog.toml", "to_be_c1.bpmn", "to_be_c2.bpmn", "to_be.bpmn"]
HAND_EDIT = ('name="Run functional tests"', 'name="Run all functional tests"')


def preset() -> dict[str, str]:
    """The preset files as the worker hands them to the studio: file name -> text."""
    return {name: (MODELS / name).read_text() for name in PRESET_FILES}


def as_is() -> tuple[str, dict]:
    return AS_IS.read_text(), tomllib.loads(AS_IS_PARAMS.read_text())


@pytest.fixture(scope="module")
def catalog():
    return load_catalog(MODELS / "to_be.catalog.toml", model=read_bpmn(AS_IS), params=load_parameters(AS_IS_PARAMS))


def change_sets(ids: list[str]) -> list[list[str]]:
    return [list(combo) for k in range(len(ids) + 1) for combo in combinations(ids, k)]


def through_the_page(design: dict) -> tuple[str, dict]:
    """A design after the parameter panel loaded it and sent it back as JSON."""
    params = default_parameters(design["xml"], json.loads(json.dumps(design["params"])))["params"]
    return design["xml"], params


# ---------- what the current design is ----------


def test_suggestions_names_the_change_set_of_every_catalog_design(catalog):
    for change_ids in change_sets(catalog.ids):
        xml, params = through_the_page(apply_suggestion(AS_IS.read_text(), change_ids, preset()))

        state = suggestions(xml, preset(), params=params)

        assert state["available"] is True
        assert state["applied"] == change_ids, change_ids
        assert state["exact"] is True, change_ids


def test_a_value_set_by_hand_drops_the_parameter_change_it_overrides_and_is_not_exact():
    xml, params = through_the_page(apply_suggestion(AS_IS.read_text(), ["C1", "C4"], preset()))
    edited = set_parameter(xml, params, "lanes.Lane_QualityControl", {"capacity": 10})["params"]

    state = suggestions(xml, preset(), params=edited)

    assert state["applied"] == ["C1"]
    assert state["exact"] is False


def test_a_hand_edit_elsewhere_keeps_the_applied_changes_but_is_not_exact():
    xml, params = through_the_page(apply_suggestion(AS_IS.read_text(), ["C2", "C3"], preset()))
    edited = set_parameter(xml, params, "tasks.Task_BuildApplication", {"duration": {"triangular": [5, 10, 20]}})["params"]

    state = suggestions(xml, preset(), params=edited)

    assert state["applied"] == ["C2", "C3"]
    assert state["exact"] is False


def test_the_catalogs_values_set_by_hand_count_as_the_change():
    xml, params = as_is()
    edited = set_parameter(xml, params, "lanes.Lane_QualityControl", {"capacity": 9})["params"]

    state = suggestions(xml, preset(), params=edited)

    assert state["applied"] == ["C4"]
    assert state["exact"] is True  # only the rationale differs, and the simulation doesn't read it


def test_after_a_hand_edit_of_the_diagram_nothing_is_applied_and_the_panel_is_unavailable():
    xml, params = as_is()
    edited = xml.replace(*HAND_EDIT)

    state = suggestions(edited, preset(), params=params)

    assert state["available"] is False
    assert state["applied"] is None
    assert state["exact"] is None
    with pytest.raises(ValueError, match="hand"):
        apply_suggestion(edited, ["C1"], preset())


def test_undo_returns_to_the_previous_combination_exactly():
    # The panel's steps: apply C1, then C3, then undo C3 (apply what is applied, minus C3).
    first = apply_suggestion(AS_IS.read_text(), ["C1"], preset())
    xml, params = through_the_page(first)
    then = apply_suggestion(xml, suggestions(xml, preset(), params=params)["applied"] + ["C3"], preset())
    xml, params = through_the_page(then)
    applied = suggestions(xml, preset(), params=params)["applied"]
    assert applied == ["C1", "C3"]

    undone = apply_suggestion(xml, [i for i in applied if i != "C3"], preset())

    assert undone == first
    assert through_the_page(undone) == through_the_page(first)


# ---------- what a step changed, for the highlight ----------


def step(before: list[str], after: list[str]) -> dict:
    """diff_designs between two catalog designs, as the panel calls it after applying."""
    old = apply_suggestion(AS_IS.read_text(), before, preset())
    new = apply_suggestion(old["xml"], after, preset())
    return diff_designs(old["xml"], old["params"], new["xml"], new["params"])


def ids(rows: list[dict]) -> set[str]:
    return {row["id"] for row in rows}


def test_applying_c1_adds_the_and_gateways_and_reroutes_the_checks():
    # Expected from models/to_be_changelog.md, C1.
    diff = step([], ["C1"])

    assert ids(diff["added"]) == {
        "Gateway_ChecksSplit", "Gateway_ChecksJoin",
        "Flow_CodeReviewStarted", "Flow_FunctionalTestsStarted", "Flow_SecurityTestsStarted", "Flow_AcceptanceTestsStarted",
        "Flow_ChecksCompleted",
    }
    assert ids(diff["rerouted"]) == {"Flow_TestsStarted", "Flow_CodeReviewed", "Flow_FunctionsTested", "Flow_SecurityTested", "Flow_AcceptanceTested"}
    assert diff["removed"] == []
    assert diff["parameters"] == []


def test_applying_c2_adds_the_retest_removes_the_old_join_and_gives_the_new_task_its_duration():
    # Expected from models/to_be_changelog.md, C2.
    diff = step([], ["C2"])

    assert ids(diff["added"]) == {"Task_RetestFixedDefects", "Gateway_RetestJoin", "Flow_DefectsRetested", "Flow_TestRoundCompleted"}
    assert ids(diff["removed"]) == {"Gateway_TestJoin", "Flow_TestsStarted"}
    assert ids(diff["rerouted"]) == {"Flow_DefectsFixed", "Flow_AcceptanceTested", "Flow_ReleaseCandidateReady"}
    assert diff["parameters"] == ["tasks.Task_RetestFixedDefects"]
    assert {row["id"]: row["label"] for row in diff["added"]}["Task_RetestFixedDefects"] == "Retest fixed defects"


def test_parameter_changes_only_change_their_entries():
    assert step(["C1"], ["C1", "C3"]) == {
        "added": [], "removed": [], "rerouted": [],
        "parameters": ["tasks.Task_SpecifyRequirements", "gateways.Gateway_TestSplit"],
    }
    assert step(["C1", "C3"], ["C1", "C3", "C4"])["parameters"] == ["lanes.Lane_QualityControl"]


def test_undoing_a_step_changes_the_same_elements_the_other_way():
    forward = step([], ["C2", "C4"])
    back = step(["C2", "C4"], [])

    assert ids(back["added"]) == ids(forward["removed"])
    assert ids(back["removed"]) == ids(forward["added"])
    assert ids(back["rerouted"]) == ids(forward["rerouted"])
    assert set(back["parameters"]) == set(forward["parameters"]) - {"tasks.Task_RetestFixedDefects"}  # its task is gone


def test_a_layout_move_or_a_new_rationale_is_no_change():
    xml, params = as_is()
    moved = xml.replace('<dc:Bounds x="', '<dc:Bounds x="1', 1)
    assert moved != xml
    renamed = set_parameter(xml, params, "lanes.Lane_QualityControl", {"capacity": 8})["params"]

    assert diff_designs(xml, params, moved, renamed) == {"added": [], "removed": [], "rerouted": [], "parameters": []}
