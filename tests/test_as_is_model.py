"""The corrected as-is model: the project's source of truth for the as-is process."""

import math
import re
from dataclasses import replace
from pathlib import Path
from xml.etree import ElementTree

from bpmopt.analysis import cycle_times
from bpmopt.bpmn import read_bpmn
from bpmopt.flow_analysis import theoretical_cycle_time
from bpmopt.lint import lint
from bpmopt.parameters import load_parameters
from bpmopt.simulation import simulate

ROOT = Path(__file__).parents[1]
MODEL = ROOT / "models" / "as_is.bpmn"
PARAMETERS = ROOT / "models" / "as_is.params.toml"
CHANGE_LOG = ROOT / "models" / "as_is_changelog.md"
ORIGINAL = ROOT / "current_process.bpmn"


def test_corrected_as_is_model_lints_clean():
    assert lint(MODEL) == []


def test_corrected_as_is_model_simulates_to_both_outcomes():
    model = read_bpmn(MODEL)
    log = simulate(model, load_parameters(PARAMETERS), n_cases=200, seed=1)

    traces = log.groupby("case_id").activity_id.agg(list)
    assert len(traces) == 200
    assert traces.str[0].eq("Start_RequestReceived").all()
    # About 10% of proposals are rejected, so 200 cases reach both outcomes.
    assert set(traces.str[-1]) == {"End_ProjectClosed", "End_ProposalRejected"}
    # The four checks that used to be one compound "test" task are timed separately.
    tests = {"Task_ReviewSourceCode", "Task_RunFunctionalTests", "Task_RunSecurityTests", "Task_RunAcceptanceTests"}
    assert tests <= set(log.activity_id)


def test_every_flow_node_and_flow_has_a_diagram_shape():
    """bpmn-js only draws what has DI, so a missing shape or edge is an invisible element."""
    root = ElementTree.parse(MODEL).getroot()
    drawn = {el.get("bpmnElement") for el in root.iter() if el.tag.endswith(("BPMNShape", "BPMNEdge"))}
    model = read_bpmn(MODEL)

    assert set(model.nodes) | set(model.flows) | set(model.lanes) <= drawn


def test_change_log_accounts_for_every_element_of_the_original_model():
    original = read_bpmn(ORIGINAL)
    mentioned = set(re.findall(r"`([^`]+)`", CHANGE_LOG.read_text(encoding="utf-8")))

    missing = (set(original.nodes) | set(original.flows) | set(original.lanes)) - mentioned
    assert not missing, f"change log doesn't mention: {sorted(missing)}"



def test_flow_analysis_of_the_as_is_model_agrees_with_its_simulation():
    # The as-is model has a "Proposal rejected" end event on a rework split and
    # several rework loops. The cross-check must work on it, not only on fixtures.
    # Flow analysis has no waiting (§7.1), so the lanes are unlimited here.
    model = read_bpmn(MODEL)
    params = replace(load_parameters(PARAMETERS), lane_capacities={})
    log = simulate(model, params, n_cases=10_000, seed=1)

    ct = cycle_times(log)
    sem = ct.std() / math.sqrt(len(ct))
    assert abs(ct.mean() - theoretical_cycle_time(model, params)) <= 4 * sem
