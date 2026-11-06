"""The flow demo page (web/demo/): its content file covers both models, and its numbers come from the data files.

The page's JS is checked in Node where Node is installed (tests/demo_state.test.mjs and
web/demo/figures.js); without Node those tests are skipped.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from bpmopt.bpmn import read_bpmn
from bpmopt.flow_analysis import loop_back_flows

ROOT = Path(__file__).parents[1]
DEMO = ROOT / "web" / "demo"
MODELS = {"as_is": ROOT / "models" / "as_is.bpmn", "to_be": ROOT / "models" / "to_be.bpmn"}
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="Node is not installed")


@pytest.fixture(scope="module")
def content():
    return json.loads((DEMO / "demo.vi.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def replay():
    return json.loads((DEMO / "replay.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def results():
    return json.loads((ROOT / "web" / "results.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("model_id", MODELS)
def test_the_content_names_every_task_and_lane_of_both_models(content, model_id):
    model = read_bpmn(MODELS[model_id])
    tasks = {n.id for n in model.nodes_of_type("task")}
    assert tasks <= set(content["activities"])
    assert set(model.lanes) <= set(content["lanes"])
    assert all(content["activities"][t].strip() for t in tasks)


def test_the_content_has_no_names_for_tasks_that_no_model_has(content):
    tasks = {n.id for path in MODELS.values() for n in read_bpmn(path).nodes_of_type("task")}
    assert set(content["activities"]) == tasks


@pytest.mark.parametrize("model_id", MODELS)
def test_every_loop_has_a_label_and_a_rework_rate_in_the_replay(content, replay, model_id):
    loops = set(loop_back_flows(read_bpmn(MODELS[model_id])))
    scenario = next(s for s in replay["scenarios"] if s["id"] == model_id)
    assert loops <= set(content["loops"])
    assert loops == {r["gateway_id"] for r in scenario["rework"]}


def test_the_content_describes_every_change_of_the_full_design(content, replay, results):
    to_be = next(s for s in replay["scenarios"] if s["id"] == "to_be")
    assert set(to_be["changes"]) == set(results["headline"]["changes"]) == set(content["changes"])


def _strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for v in node.values():
            yield from _strings(v)
    elif isinstance(node, list):
        for v in node:
            yield from _strings(v)


def test_the_content_types_no_result_numbers(content):
    # Numbers come from results.json or replay.json through {placeholders}. Allowed: change IDs and the CI level.
    for s in _strings(content):
        assert not re.search(r"\d", re.sub(r"C[1-4]|95%", "", s)), s
    assert content["result"]["goal_share"] == 0.2  # the objective from the report's problem section


def test_the_content_reads_without_em_dashes(content):
    assert not any("—" in s for s in _strings(content))


@needs_node
def test_the_result_panel_numbers_are_the_official_ones_from_results_json(results):
    script = (
        "import { figures } from './web/demo/figures.js';"
        "import fs from 'node:fs';"
        "console.log(JSON.stringify(figures(JSON.parse(fs.readFileSync('web/results.json')))));"
    )
    out = subprocess.run([NODE, "--input-type=module", "-e", script], cwd=ROOT, capture_output=True, text=True, check=True)
    shown = json.loads(out.stdout)

    def scenario(changes):
        return next(s for s in results["scenarios"] if sorted(s["changes"]) == sorted(changes))

    assert shown["replications"] == results["meta"]["replications"] == 30
    assert shown["cases"] == results["meta"]["case_count"]
    for key, changes in [("asIs", []), ("full", ["C1", "C2", "C3", "C4"]), ("best", ["C1", "C2", "C4"])]:
        s = scenario(changes)
        assert sorted(shown[key]["changes"]) == changes
        assert shown[key]["cycleTime"] == s["cycle_time"]["mean"]
        assert shown[key]["saving"] == s["saving"]
        assert shown[key]["share"] == s["saving_share"]
    assert results["headline"]["changes"] == ["C1", "C2", "C3", "C4"]
    assert results["headline"]["best"] == ["C1", "C2", "C4"]
    # The numbers in the spec: 140.8, 104.5, 36.3 days, 25.7% (CI 22.7% to 28.8%), C1+C2+C4 27.8%.
    assert round(shown["asIs"]["cycleTime"]["value"], 1) == 140.8
    assert round(shown["full"]["cycleTime"]["value"], 1) == 104.5
    assert round(shown["full"]["saving"]["value"], 1) == 36.3
    assert round(shown["full"]["share"]["value"] * 100, 1) == 25.7
    assert round(shown["best"]["share"]["value"] * 100, 1) == 27.8


@needs_node
@pytest.mark.parametrize("model_id", MODELS)
def test_the_layout_puts_every_task_in_its_bpmn_lane(model_id):
    script = (
        "import { buildLayout, LANES } from './web/demo/layout.js';"
        f"const l = buildLayout('{model_id}');"
        "console.log(JSON.stringify({ lanes: LANES, boxes: Object.fromEntries(Object.values(l.boxes).map((b) => [b.id, b.lane])) }));"
    )
    out = subprocess.run([NODE, "--input-type=module", "-e", script], cwd=ROOT, capture_output=True, text=True, check=True)
    layout = json.loads(out.stdout)
    model = read_bpmn(MODELS[model_id])
    assert layout["lanes"] == list(model.lanes)
    assert layout["boxes"] == {n.id: n.lane for n in model.nodes_of_type("task")}


@needs_node
def test_the_page_state_module_passes_its_node_tests():
    out = subprocess.run([NODE, "--test", "tests/demo_state.test.mjs"], cwd=ROOT, capture_output=True, text=True)
    assert out.returncode == 0, out.stdout + out.stderr


def test_the_page_reads_text_and_numbers_only_from_its_data_files():
    page = (DEMO / "index.html").read_text(encoding="utf-8")
    body = re.sub(r"<style>.*?</style>|<script.*?</script>", "", page, flags=re.S)
    visible = re.sub(r"<[^>]+>", " ", body)
    assert not re.sub(r"Mô phỏng quy trình", "", visible).strip()  # only the <title> fallback
    app = (DEMO / "app.js").read_text(encoding="utf-8")
    for path in ["demo.vi.json", "replay.json", "../results.json"]:
        assert path in app


def test_the_report_links_to_the_demo():
    page = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    assert 'href: "demo/"' in page
