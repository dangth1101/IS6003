"""The flow demo page (web/demo/): its content file covers both models, and its numbers come from the data files.

The page's JS is checked in Node where Node is installed (tests/demo_state.test.mjs and
web/demo/figures.js); without Node those tests are skipped.
"""

import json
import re
import shutil
import subprocess
import tomllib
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
    loops = loop_back_flows(read_bpmn(MODELS[model_id]))
    scenario = next(s for s in replay["scenarios"] if s["id"] == model_id)
    assert all("{rate}" in content["conditions"][flow] for flow in loops.values())
    assert set(loops) == {r["gateway_id"] for r in scenario["rework"]}


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
    # Numbers come from results.json or replay.json through {placeholders}. Allowed: change IDs, the CI level
    # and the method names graph2vec and node2vec.
    for s in _strings(content):
        assert not re.search(r"\d", re.sub(r"C[1-4]|95%|(?:graph|node)2vec", "", s)), s
    assert content["result"]["goal_share"] == 0.2  # the objective from the report's problem section


STAND_INS = re.compile(r"[→←×—–•·…]|-{3,}|[\U0001F300-\U0001FAFF☀-➿]")


def test_the_content_reads_like_a_person_wrote_it(content):
    # No arrows, multiplication signs, dashes, bullets or emoji standing in for words.
    for s in _strings(content):
        assert not STAND_INS.search(s), s


def test_the_page_code_types_no_stand_in_symbols_either():
    for name in ["app.js", "layout.js", "index.html"]:
        code = (DEMO / name).read_text(encoding="utf-8")
        strings = re.findall(r"`[^`]*`|\"[^\"\n]*\"|'[^'\n]*'", code)
        visible = re.sub(r"<[^>]+>", " ", re.sub(r"<style>.*?</style>|<script.*?</script>", "", code, flags=re.S)) if name.endswith(".html") else ""
        for s in [*strings, visible]:
            assert not STAND_INS.search(s), (name, s)


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


def test_the_groups_step_names_every_loop_and_every_attribute(content):
    groups = content["groups"]
    assert set(groups["loop_parts"]) == set(loop_back_flows(read_bpmn(MODELS["as_is"])))
    page = tomllib.loads((ROOT / "src/bpmopt/content/page.en.toml").read_text(encoding="utf-8"))
    assert set(groups["features"]) == set(page["features"])


@needs_node
def test_the_groups_step_shows_the_groups_from_results_json(results):
    script = (
        "import { caseGroups, overallDays } from './web/demo/groups.js';"
        "import fs from 'node:fs';"
        "const r = JSON.parse(fs.readFileSync('web/results.json'));"
        "console.log(JSON.stringify({ rows: caseGroups(r), overall: overallDays(r) }));"
    )
    out = subprocess.run([NODE, "--input-type=module", "-e", script], cwd=ROOT, capture_output=True, text=True, check=True)
    shown = json.loads(out.stdout)
    groups = {g["id"]: g for g in results["clusters"]["cases"]["groups"]}

    assert sorted(row["id"] for row in shown["rows"]) == sorted(groups)
    assert [row["days"] for row in shown["rows"]] == sorted((g["cycle_time"]["mean"] for g in groups.values()), reverse=True)
    for row in shown["rows"]:
        g = groups[row["id"]]
        assert row["cases"] == g["case_count"]
        assert row["loops"] == [loop["gateway_id"] for loop in g["loops"] if loop["mean"] >= 0.5]
    assert shown["overall"] == results["baseline"]["cycle_time"]["mean"]


@needs_node
def test_the_findings_of_step_three_are_read_off_the_groups(results):
    script = (
        "import { findings } from './web/demo/groups.js';"
        "import fs from 'node:fs';"
        "console.log(JSON.stringify(findings(JSON.parse(fs.readFileSync('web/results.json')))));"
    )
    out = subprocess.run([NODE, "--input-type=module", "-e", script], cwd=ROOT, capture_output=True, text=True, check=True)
    shown = json.loads(out.stdout)
    groups = results["clusters"]["cases"]["groups"]
    total = sum(g["case_count"] for g in groups)
    clean = next(g for g in groups if all(loop["mean"] < 0.5 for loop in g["loops"]))
    slowest = max(groups, key=lambda g: g["cycle_time"]["mean"])
    qc = [g for g in groups if any(loop["gateway_id"] == "Gateway_TestSplit" and loop["mean"] >= 0.5 for loop in g["loops"])]

    assert shown["clean"]["share"] == pytest.approx(clean["case_count"] / total)
    assert shown["slowest"]["days"] == slowest["cycle_time"]["mean"]
    assert shown["slowest"]["ratio"] == pytest.approx(slowest["cycle_time"]["mean"] / clean["cycle_time"]["mean"])
    assert shown["qc"]["share"] == pytest.approx(sum(g["case_count"] for g in qc) / total)
    assert shown["qc"]["high"] == pytest.approx(max(g["cycle_time"]["mean"] for g in qc) - clean["cycle_time"]["mean"])


def _drawing(model_id, metrics):
    """What the page draws for one model: its nodes (type, lane) and its sequence flows, from layout.js."""
    script = (
        "import { buildLayout, LANES } from './web/demo/layout.js';"
        f"const l = buildLayout('{model_id}', '{metrics}');"
        "console.log(JSON.stringify({ lanes: LANES,"
        " nodes: Object.fromEntries(Object.values(l.nodes).map((n) => [n.id, [n.type, n.lane]])),"
        " flows: Object.fromEntries(Object.values(l.flows).map((f) => [f.id, [f.source, f.target, f.pts.length, !!f.label]])) }));"
    )
    out = subprocess.run([NODE, "--input-type=module", "-e", script], cwd=ROOT, capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


@needs_node
@pytest.mark.parametrize("metrics", ["normal", "compact"])
@pytest.mark.parametrize("model_id", MODELS)
def test_the_drawing_has_exactly_the_elements_and_flows_of_the_bpmn_model(model_id, metrics):
    # Every event, task and gateway of the model, with its BPMN type and lane, and nothing else;
    # every sequence flow between the same two elements. The demo can't drift from the model.
    drawn = _drawing(model_id, metrics)
    model = read_bpmn(MODELS[model_id])
    assert drawn["lanes"] == list(model.lanes)
    assert drawn["nodes"] == {n.id: [n.element_type, n.lane] for n in model.nodes.values()}
    assert {f: v[:2] for f, v in drawn["flows"].items()} == {f.id: [f.source, f.target] for f in model.flows.values()}
    assert all(v[2] >= 2 for v in drawn["flows"].values())


@needs_node
@pytest.mark.parametrize("model_id", MODELS)
def test_every_arc_out_of_an_xor_split_carries_its_condition_and_loops_carry_the_rework_share(content, model_id):
    # Book p.190: label the conditions on the arcs of an XOR-split, not yes/no on the gateway.
    drawn = _drawing(model_id, "normal")
    model = read_bpmn(MODELS[model_id])
    loops = set(loop_back_flows(model).values())
    for split in model.xor_splits():
        for flow in model.outgoing(split.id):
            text = content["conditions"][flow.id]
            assert drawn["flows"][flow.id][3], flow.id
            assert ("{rate}" in text) == (flow.id in loops), flow.id
            assert text.strip().lower() not in {"yes", "no", "có", "không"}
    labelled = {f for f, v in drawn["flows"].items() if v[3]}
    assert labelled == {f.id for s in model.xor_splits() for f in model.outgoing(s.id)}


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
