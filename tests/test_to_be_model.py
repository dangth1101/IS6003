"""The to-be models and the change catalog of the redesign (ticket 15).

Catalog: models/to_be.catalog.toml on the as-is model. C1 runs the four checks
in parallel and C2 reruns only the failed checks after a fix (structural, one
BPMN file each plus models/to_be.bpmn for both). C3 triages risky cases and C4
adds a QC tester (parameter-only).

The to-be files may break G7 (more than 30 flow nodes): the book's remedy is
decomposition into sub-processes, which the supported subset doesn't have. The
student accepted that warning for the to-be models only (models/to_be_changelog.md).
"""

import re
from pathlib import Path
from xml.etree import ElementTree

import pytest

from bpmopt.bpmn import read_bpmn
from bpmopt.lint import ERROR, lint
from bpmopt.parameters import load_parameters
from bpmopt.scenarios import load_catalog
from bpmopt.simulation import simulate

ROOT = Path(__file__).parents[1]
MODELS = ROOT / "models"
TO_BE_FILES = ["to_be_c1.bpmn", "to_be_c2.bpmn", "to_be.bpmn"]
CATALOG = MODELS / "to_be.catalog.toml"


@pytest.fixture(scope="module")
def catalog():
    model = read_bpmn(MODELS / "as_is.bpmn")
    return load_catalog(CATALOG, model=model, params=load_parameters(MODELS / "as_is.params.toml", model))


@pytest.mark.parametrize("name", TO_BE_FILES)
def test_to_be_model_has_no_lint_errors_and_only_the_accepted_g7_warning(name):
    violations = lint(MODELS / name)

    assert [v for v in violations if v.severity == ERROR] == []
    assert {v.rule for v in violations} <= {"G7"}


@pytest.mark.parametrize("name", TO_BE_FILES)
def test_every_element_of_a_to_be_model_has_a_diagram_shape(name):
    """bpmn-js only draws what has DI, so a missing shape or edge is an invisible element."""
    root = ElementTree.parse(MODELS / name).getroot()
    drawn = {el.get("bpmnElement") for el in root.iter() if el.tag.endswith(("BPMNShape", "BPMNEdge"))}
    model = read_bpmn(MODELS / name)

    assert set(model.nodes) | set(model.flows) | set(model.lanes) <= drawn


def test_c1_runs_the_four_checks_between_an_and_split_and_an_and_join():
    model = read_bpmn(MODELS / "to_be_c1.bpmn")
    checks = {"Task_ReviewSourceCode", "Task_RunFunctionalTests", "Task_RunSecurityTests", "Task_RunAcceptanceTests"}

    split, join = model.nodes["Gateway_ChecksSplit"], model.nodes["Gateway_ChecksJoin"]
    assert split.element_type == join.element_type == "parallelGateway"
    assert {f.target for f in model.outgoing(split.id)} == checks
    assert {f.source for f in model.incoming(join.id)} == checks
    # The rework decision after the checks is the as-is one, so its parameters still apply.
    assert [f.target for f in model.outgoing(join.id)] == ["Gateway_TestSplit"]
    assert {f.id for f in model.outgoing("Gateway_TestSplit")} == {"Flow_TestsPassed", "Flow_DefectsFound"}


def test_c2_sends_a_fixed_case_through_one_retest_instead_of_all_four_checks():
    model = read_bpmn(MODELS / "to_be_c2.bpmn")

    retest = model.nodes["Task_RetestFixedDefects"]
    assert retest.label == "Retest fixed defects"
    assert retest.lane == "Lane_QualityControl"
    assert [f.target for f in model.outgoing("Task_FixDefects")] == [retest.id]
    # The retest and the first test round meet at an XOR join right before the rework decision.
    assert [f.target for f in model.outgoing(retest.id)] == ["Gateway_RetestJoin"]
    assert {f.source for f in model.incoming("Gateway_RetestJoin")} == {retest.id, "Task_RunAcceptanceTests"}
    assert [f.target for f in model.outgoing("Gateway_RetestJoin")] == ["Gateway_TestSplit"]
    # Same flow IDs out of the rework decision, so the as-is branch parameters still apply.
    assert {f.id for f in model.outgoing("Gateway_TestSplit")} == {"Flow_TestsPassed", "Flow_DefectsFound"}
    # The join in front of the checks has nothing left to join, so it is gone (G1).
    assert "Gateway_TestJoin" not in model.nodes


def test_the_full_to_be_has_both_structural_changes():
    model = read_bpmn(MODELS / "to_be.bpmn")

    assert model.process_id == "Process_AppDevelopment_ToBe"
    assert [f.target for f in model.outgoing("Gateway_ReleaseJoin")] == ["Gateway_ChecksSplit"]
    assert [f.target for f in model.outgoing("Gateway_ChecksJoin")] == ["Gateway_RetestJoin"]
    assert {f.source for f in model.incoming("Gateway_RetestJoin")} == {"Gateway_ChecksJoin", "Task_RetestFixedDefects"}
    assert [f.target for f in model.outgoing("Task_FixDefects")] == ["Task_RetestFixedDefects"]
    assert len(model.nodes) == 33


def test_the_as_is_model_still_lints_fully_clean():
    # G7 warnings are accepted on the to-be variants only.
    assert lint(MODELS / "as_is.bpmn") == []


def test_change_log_accounts_for_every_element_the_redesign_adds_or_removes():
    as_is = read_bpmn(MODELS / "as_is.bpmn")
    text = (MODELS / "to_be_changelog.md").read_text(encoding="utf-8")
    mentioned = set(re.findall(r"`([^`]+)`", text))

    for name in TO_BE_FILES:
        to_be = read_bpmn(MODELS / name)
        rerouted = {
            f.id for f in to_be.flows.values() if f.id in as_is.flows and (f.source, f.target) != (as_is.flows[f.id].source, as_is.flows[f.id].target)
        }
        differ = (set(to_be.nodes) ^ set(as_is.nodes)) | (set(to_be.flows) ^ set(as_is.flows)) | rerouted
        assert differ <= mentioned, f"{name}: change log doesn't mention {sorted(differ - mentioned)}"
        assert f"`{name}`" in text
    assert "G7" in text


def test_the_catalog_has_four_changes_each_tied_to_a_driver_and_an_appendix_a_heuristic(catalog):
    assert catalog.ids == ["C1", "C2", "C3", "C4"]
    heuristics = {e["id"]: (e["heuristic"]["name"], e["heuristic"]["ref"]) for e in catalog.entries()}
    assert heuristics == {
        "C1": ("Parallelism", "Appendix A.3"),
        "C2": ("Activity elimination", "Appendix A.2"),
        "C3": ("Triage", "Appendix A.2"),
        "C4": ("Extra resources", "Appendix A.4"),
    }
    # A change that weakens a quality check says so on the Devil's Quadrangle.
    for entry in catalog.entries():
        if entry["trade_off"]["quality"] == "worse":
            assert entry["trade_off"]["note"]


def test_every_combination_resolves_to_its_model(catalog):
    expected = {
        frozenset(): "Process_AppDevelopment_AsIs",
        frozenset({"C1"}): "Process_AppDevelopment_ToBe_C1",
        frozenset({"C2"}): "Process_AppDevelopment_ToBe_C2",
        frozenset({"C1", "C2"}): "Process_AppDevelopment_ToBe",
    }

    assert len(catalog.scenarios) == 2**4
    for combo, (model, params) in catalog.scenarios.items():
        assert model.process_id == expected[combo & {"C1", "C2"}]
        assert ("Task_RetestFixedDefects" in params.task_durations) == ("C2" in combo)


def test_c3_leaves_a_simple_internal_app_as_it_is_and_shifts_effort_to_risky_cases(catalog):
    _, as_is = catalog.resolve([])
    _, triaged = catalog.resolve(["C3"])
    simple = {"complexity": 1, "security_level": 1, "integrations": 2}
    risky = {"complexity": 3, "security_level": 3, "integrations": 2}

    def spec_days(params, case):
        return params.task_durations["Task_SpecifyRequirements"].mean_given(case)

    def defect_rate(params, case):
        return params.branch_probabilities["Gateway_TestSplit"].probabilities(case)["Flow_DefectsFound"]

    assert spec_days(triaged, simple) == pytest.approx(spec_days(as_is, simple))
    assert defect_rate(triaged, simple) == pytest.approx(defect_rate(as_is, simple))
    # Riskiest case: 10% of the as-is base more per step above 1 on both attributes, 4 steps in all.
    base = (5 + 8 + 16) / 3
    assert spec_days(triaged, risky) == pytest.approx(spec_days(as_is, risky) + 0.4 * base)
    assert defect_rate(triaged, risky) < defect_rate(as_is, risky)


def test_c4_adds_one_qc_tester(catalog):
    assert catalog.resolve([])[1].lane_capacities["Lane_QualityControl"] == 8
    assert catalog.resolve(["C4"])[1].lane_capacities["Lane_QualityControl"] == 9


@pytest.mark.parametrize("combo", [(), ("C1",), ("C2",), ("C3",), ("C4",), ("C1", "C2", "C3", "C4")])
def test_each_scenario_simulates_to_go_live(catalog, combo):
    model, params = catalog.resolve(combo)

    log = simulate(model, params, n_cases=40, seed=3)

    traces = log.groupby("case_id").activity_id.agg(list)
    assert len(traces) == 40
    assert set(traces.str[-1]) <= {"End_ProjectClosed", "End_ProposalRejected"}
    assert "Task_StartOperation" in set(log.activity_id)
