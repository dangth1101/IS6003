"""The studio seam: bpmopt.studio and the string / dict readers it builds on.

The studio page runs these in the browser (Pyodide), so inputs are BPMN XML
strings and parameter dicts, never file paths, and outputs are JSON-shaped.
"""

import json
import re
import subprocess
import sys
import tomllib
import zipfile
from itertools import combinations
from pathlib import Path

import numpy as np
import pytest

from bpmopt.analysis import baseline_metrics
from bpmopt.bpmn import parse_bpmn, read_bpmn
from bpmopt.lint import lint
from bpmopt.parameters import load_parameters, parse_parameters
from bpmopt.results import load_page_text
from bpmopt.scenarios import Catalog, estimate, find_scenario, full_design, load_catalog, replication_seeds, run_scenarios
from bpmopt.simulation import simulate
from bpmopt.studio import apply_suggestion, compare, default_parameters, lint_xml, simulate_summary, suggestions

ROOT = Path(__file__).parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
AS_IS = ROOT / "models" / "as_is.bpmn"
AS_IS_PARAMS = ROOT / "models" / "as_is.params.toml"


def as_is_preset() -> tuple[str, dict]:
    """The as-is preset as the page sends it: the BPMN text and the parameter file as a dict."""
    return AS_IS.read_text(), tomllib.loads(AS_IS_PARAMS.read_text())


def test_a_bpmn_string_reads_to_the_same_model_as_its_file():
    assert parse_bpmn(AS_IS.read_text()) == read_bpmn(AS_IS)


def test_a_parameter_dict_loads_to_the_same_parameters_as_its_file():
    raw = tomllib.loads(AS_IS_PARAMS.read_text())

    assert parse_parameters(raw) == load_parameters(AS_IS_PARAMS)


def test_simulate_summary_gives_the_scenario_runners_as_is_numbers():
    # The notebook's path: the empty scenario of a catalog, with the same seed, cases and replications.
    as_is_only = Catalog("test", (), {frozenset(): (read_bpmn(AS_IS), load_parameters(AS_IS_PARAMS))})
    (expected,) = run_scenarios(as_is_only, n_cases=100, seed=7, replications=3)

    summary = simulate_summary(*as_is_preset(), n_cases=100, seed=7, replications=3)

    assert summary["replication_means"] == expected["replication_means"]
    assert summary["cycle_time"] == expected["cycle_time"]  # mean, median and P90, each with its CI


def test_simulate_summary_of_the_as_is_preset_matches_the_parity_fixture():
    # The studio's default run. The browser check compares against the same file.
    parity = json.loads((ROOT / "tests" / "fixtures" / "studio_parity.json").read_text())

    summary = simulate_summary(*as_is_preset(), n_cases=parity["n_cases"], seed=parity["seed"], replications=parity["replications"])

    assert summary["replication_means"] == parity["replication_means"]
    assert summary["cycle_time"]["mean"] == parity["cycle_time"]["mean"]


def test_simulate_summary_averages_the_notebooks_baseline_measures_over_replications():
    # Per replication, the same measures as the report's baseline section, then a mean and 95% CI over replications.
    model, params = read_bpmn(AS_IS), load_parameters(AS_IS_PARAMS)
    seeds = replication_seeds(5, 3)
    runs = [baseline_metrics(simulate(model, params, n_cases=60, seed=s), model, ends_at=params.cycle_time_end) for s in seeds]

    summary = simulate_summary(*as_is_preset(), n_cases=60, seed=5, replications=3)

    assert summary["processing_time"]["mean"] == estimate(np.array([run["processing_time"]["mean"] for run in runs]))
    assert summary["waiting_time"]["mean"] == estimate(np.array([run["waiting_time"]["mean"] for run in runs]))
    assert summary["cycle_time_efficiency"] == estimate(np.array([run["cycle_time_efficiency"] for run in runs]))
    rework = {row["gateway_id"]: row["rate"] for row in summary["rework"]}
    assert rework == {
        row["gateway_id"]: estimate(np.array([r["rate"] for run in runs for r in run["rework"] if r["gateway_id"] == row["gateway_id"]]))
        for row in runs[0]["rework"]
    }
    waiting = {row["activity_id"]: row["mean"] for row in summary["waiting_by_activity"]}
    assert waiting["Task_RunFunctionalTests"] == estimate(
        np.array([r["mean"] for run in runs for r in run["waiting_by_activity"] if r["activity_id"] == "Task_RunFunctionalTests"])
    )


def test_simulate_summary_lists_waiting_per_activity_longest_first_with_labels():
    summary = simulate_summary(*as_is_preset(), n_cases=60, seed=5, replications=3)

    means = [row["mean"]["value"] for row in summary["waiting_by_activity"]]
    assert means == sorted(means, reverse=True)
    model = read_bpmn(AS_IS)
    assert all(row["label"] == model.nodes[row["activity_id"]].label for row in summary["waiting_by_activity"])
    assert all(row["label"] == model.nodes[row["gateway_id"]].label for row in summary["rework"])


def test_simulate_summary_gives_the_book_utilisation_per_limited_lane():
    # single_task.rho05: one reviewer, a fixed 1-day review, 0.5 arrivals a day, so rho = 0.5 x 1 / 1 exactly (Eq. 7.8).
    xml = (FIXTURES / "single_task.bpmn").read_text()
    params = tomllib.loads((FIXTURES / "single_task.rho05.params.toml").read_text())

    summary = simulate_summary(xml, params, n_cases=50, seed=3, replications=2)

    assert summary["lanes"] == [
        {"lane_id": "Lane_Review", "label": read_bpmn(FIXTURES / "single_task.bpmn").lanes["Lane_Review"], "capacity": 1,
         "utilisation": {"value": 0.5, "ci_low": 0.5, "ci_high": 0.5}}
    ]


def test_simulate_summary_reports_progress_after_each_replication():
    calls = []

    simulate_summary(*as_is_preset(), n_cases=20, seed=1, replications=3, progress=lambda done, total: calls.append((done, total)))

    assert calls == [(1, 3), (2, 3), (3, 3)]


def test_simulate_summary_is_json_serialisable():
    summary = simulate_summary(*as_is_preset(), n_cases=20, seed=1, replications=2)

    assert json.loads(json.dumps(summary)) == summary


def test_the_studio_imports_nothing_outside_the_simulation_path():
    # In the browser there is no scikit-learn or SHAP; a fresh interpreter shows what importing the studio pulls in.
    banned = ["bpmopt.ml", "bpmopt.features", "bpmopt.results", "bpmopt.planted", "sklearn", "shap"]
    code = f"import sys, bpmopt.studio; print([m for m in {banned!r} if m in sys.modules])"

    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout

    assert out.strip() == "[]"


def test_lint_xml_reports_the_same_violations_as_lint_on_the_file():
    # The original model breaks several rules, so this compares real violations, not two empty lists.
    original = ROOT / "current_process.bpmn"

    violations = lint_xml(original.read_text())

    assert violations == [
        {"rule": v.rule, "severity": v.severity, "element_id": v.element_id, "message": v.message} for v in lint(original)
    ]
    assert len(violations) > 3


@pytest.mark.parametrize(
    "xml",
    [
        "not xml",
        '<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL"><process id="P">'
        '<sequenceFlow id="Flow_Half"/></process></definitions>',
    ],
    ids=["not-xml", "flow-without-ends"],
)
def test_lint_xml_says_in_one_value_error_that_a_document_it_cannot_read_is_not_readable_bpmn(xml):
    # The page shows this message in the lint panel and blocks Run, so it must say what is wrong.
    with pytest.raises(ValueError, match="Not a readable BPMN document"):
        lint_xml(xml)


def test_a_model_without_parameters_simulates_after_default_parameters_with_every_entry_marked():
    xml = (FIXTURES / "proposal_rejected.bpmn").read_text()

    filled = default_parameters(xml)

    params = filled["params"]
    assert params["tasks"]["Task_BuildApp"]["duration"] == {"triangular": [1, 2, 4]}
    assert params["lanes"] == {lane: {"capacity": 1, "rationale": params["lanes"][lane]["rationale"]} for lane in ("Lane_Business", "Lane_Dev")}
    assert params["gateways"]["Gateway_ReviewSplit"]["branches"] == {"Flow_Approved": 1 / 3, "Flow_Revise": 1 / 3, "Flow_Rejected": 1 / 3}
    assert params["gateways"]["Gateway_TestSplit"]["branches"] == {"Flow_Passed": 0.5, "Flow_Failed": 0.5}
    assert sorted(filled["defaults"]) == sorted(
        ["arrivals", "warm_up", "lanes.Lane_Business", "lanes.Lane_Dev", "gateways.Gateway_ReviewSplit", "gateways.Gateway_TestSplit"]
        + [f"tasks.{t}" for t in ("Task_ReviewProposal", "Task_ReviseProposal", "Task_BuildApp", "Task_TestApp", "Task_FixDefects")]
    )
    assert filled["dropped"] == []
    summary = simulate_summary(xml, params, n_cases=200, seed=1, replications=2)
    assert summary["cycle_time"]["mean"]["value"] > 0


def test_the_default_arrival_rate_keeps_the_busiest_lane_about_80_percent_busy():
    # Busy enough that queues show, far enough below 1 that they settle (book p.276).
    xml = (FIXTURES / "proposal_rejected.bpmn").read_text()

    params = default_parameters(xml)["params"]

    summary = simulate_summary(xml, params, n_cases=1000, seed=2, replications=3)
    busiest = max(row["utilisation"]["value"] for row in summary["lanes"])
    assert 0.75 <= busiest <= 0.85
    assert params["warm_up"]["length"] == round(100 / params["arrivals"]["rate"])


def test_default_parameters_keeps_a_complete_parameter_set_as_it_is():
    xml, params = as_is_preset()

    filled = default_parameters(xml, params)

    assert filled == {"params": params, "defaults": [], "dropped": []}


def test_default_parameters_fills_a_new_task_and_drops_entries_for_elements_the_model_lacks():
    # The C2 model has one task more than the as-is; the parameters name a lane and a task it doesn't have.
    _, params = as_is_preset()
    params["tasks"]["Task_Gone"] = {"duration": {"fixed": 1}, "rationale": "Removed from the diagram."}
    params["lanes"]["Lane_Gone"] = {"capacity": 2, "rationale": "Removed from the diagram."}

    filled = default_parameters((ROOT / "models" / "to_be_c2.bpmn").read_text(), params)

    assert filled["defaults"] == ["tasks.Task_RetestFixedDefects"]
    assert sorted(filled["dropped"]) == ["lanes.Lane_Gone", "tasks.Task_Gone"]
    assert filled["params"]["tasks"]["Task_RunFunctionalTests"] == params["tasks"]["Task_RunFunctionalTests"]
    assert "Task_Gone" not in filled["params"]["tasks"] and "Lane_Gone" not in filled["params"]["lanes"]


def test_default_parameters_replaces_branches_that_no_longer_match_the_gateways_flows():
    # After a reconnect the old branch table names a flow the split no longer has.
    xml, params = as_is_preset()
    old = params["gateways"]["Gateway_ReleaseSplit"]
    params["gateways"]["Gateway_ReleaseSplit"] = {"branches": {"Flow_ReleaseApproved": 0.9, "Flow_Gone": 0.1}, "rationale": old["rationale"]}

    filled = default_parameters(xml, params)

    assert filled["params"]["gateways"]["Gateway_ReleaseSplit"]["branches"] == {"Flow_ReleaseApproved": 0.5, "Flow_ReleaseRejected": 0.5}
    assert filled["defaults"] == ["gateways.Gateway_ReleaseSplit"]
    assert filled["dropped"] == ["gateways.Gateway_ReleaseSplit"]


def test_defaults_stay_marked_when_the_page_sends_them_back():
    # The page keeps the filled parameters and calls default_parameters again after every edit.
    xml = (FIXTURES / "proposal_rejected.bpmn").read_text()
    first = default_parameters(xml)

    again = default_parameters(xml, first["params"])

    assert again == first


def test_a_model_with_lint_errors_gets_durations_and_branches_but_no_arrival_rate_yet():
    # The arrival rate comes from a pilot run, which needs a model that can run; it is filled once the errors are fixed.
    filled = default_parameters((ROOT / "current_process.bpmn").read_text())

    assert "arrivals" not in filled["params"] and "warm_up" not in filled["params"]
    assert len(filled["params"]["tasks"]) == 15


PRESET_FILES = ["as_is.bpmn", "as_is.params.toml", "to_be.catalog.toml", "to_be_c1.bpmn", "to_be_c2.bpmn", "to_be.bpmn"]


def preset() -> dict[str, str]:
    """The preset files as the worker hands them to the studio: file name -> text."""
    return {name: (ROOT / "models" / name).read_text() for name in PRESET_FILES}


@pytest.fixture(scope="module")
def catalog():
    return load_catalog(ROOT / "models" / "to_be.catalog.toml", model=read_bpmn(AS_IS), params=load_parameters(AS_IS_PARAMS))


def change_sets(ids: list[str]) -> list[list[str]]:
    return [list(combo) for k in range(len(ids) + 1) for combo in combinations(ids, k)]


def test_apply_suggestion_gives_the_catalogs_model_and_parameters_for_every_change_set(catalog):
    xml, _ = as_is_preset()

    for change_ids in change_sets(catalog.ids):
        applied = apply_suggestion(xml, change_ids, preset())

        model, params = catalog.resolve(change_ids)
        assert parse_bpmn(applied["xml"]) == model, change_ids
        assert parse_parameters(applied["params"], model) == params, change_ids
        assert applied["changes"] == [i for i in catalog.ids if i in change_ids]


def test_apply_suggestion_works_from_any_preset_design_so_it_can_undo():
    with_c1_c2 = apply_suggestion(AS_IS.read_text(), ["C2", "C1"], preset())

    undone = apply_suggestion(with_c1_c2["xml"], ["C1"], preset())

    assert undone == apply_suggestion(AS_IS.read_text(), ["C1"], preset())


def test_apply_suggestion_refuses_a_hand_edited_model():
    xml = AS_IS.read_text().replace('name="Run functional tests"', 'name="Run all functional tests"')
    assert xml != AS_IS.read_text()

    with pytest.raises(ValueError, match="hand"):
        apply_suggestion(xml, ["C4"], preset())


def test_apply_suggestion_refuses_a_change_the_catalog_does_not_have():
    with pytest.raises(ValueError, match="C9"):
        apply_suggestion(AS_IS.read_text(), ["C1", "C9"], preset())


def test_suggestions_lists_the_catalog_and_whether_they_apply_to_the_current_model(catalog):
    hand_edited = AS_IS.read_text().replace('name="Run functional tests"', 'name="Run all functional tests"')
    full = apply_suggestion(AS_IS.read_text(), catalog.ids, preset())

    assert suggestions(AS_IS.read_text(), preset()) == {"changes": catalog.entries(), "available": True, "applied": None, "exact": None}
    assert suggestions(full["xml"], preset())["available"] is True
    assert suggestions(hand_edited, preset())["available"] is False


@pytest.fixture(scope="module")
def runner(catalog):
    """The notebook's scenario runner on the catalog, small enough for a test."""
    return run_scenarios(catalog, n_cases=40, seed=3, replications=3)


def test_a_suggestion_simulates_to_the_scenario_runners_numbers(catalog, runner):
    for change_ids in change_sets(catalog.ids):
        applied = apply_suggestion(AS_IS.read_text(), change_ids, preset())

        summary = simulate_summary(applied["xml"], applied["params"], n_cases=40, seed=3, replications=3)

        assert summary["replication_means"] == find_scenario(runner, change_ids)["replication_means"], change_ids


def test_compare_of_the_as_is_and_the_full_design_gives_the_runners_paired_saving(catalog, runner):
    as_is = simulate_summary(*as_is_preset(), n_cases=40, seed=3, replications=3)
    full = apply_suggestion(AS_IS.read_text(), catalog.ids, preset())
    proposed = simulate_summary(full["xml"], full["params"], n_cases=40, seed=3, replications=3)

    comparison = compare(as_is, proposed)

    expected = full_design(runner)
    assert comparison["saving"] == expected["saving"]
    assert comparison["saving_share"] == expected["saving_share"]
    assert comparison["baseline"]["cycle_time"] == as_is["cycle_time"]
    assert comparison["variant"]["cycle_time"] == proposed["cycle_time"]


def test_the_studio_gives_the_reports_full_design_saving_with_the_reports_settings():
    # The lecturer's check: run the studio with the case count, replications and seed the
    # report states, and get the report's saving. The expected values are the notebook's,
    # read from the published results.json. Slow: 2,000 cases x 30 replications, twice.
    report = json.loads((ROOT / "web" / "results.json").read_text(encoding="utf-8"))
    meta, changes = report["meta"], report["headline"]["changes"]
    expected = next(s for s in report["scenarios"] if sorted(s["changes"]) == sorted(changes))
    xml, params = as_is_preset()
    assert (params["version"], params["warm_up"]["length"]) == (meta["parameter_version"], meta["warm_up"])
    run = {"n_cases": meta["case_count"], "seed": meta["seed"], "replications": meta["replications"]}

    as_is = simulate_summary(xml, params, **run)
    full = apply_suggestion(xml, changes, preset())
    comparison = compare(as_is, simulate_summary(full["xml"], full["params"], **run))

    assert comparison["variant"]["cycle_time"] == expected["cycle_time"]
    assert comparison["saving"] == expected["saving"]
    assert comparison["saving_share"] == expected["saving_share"]


def test_compare_puts_each_lane_and_activity_before_and_after_side_by_side(catalog):
    as_is = simulate_summary(*as_is_preset(), n_cases=40, seed=3, replications=3)
    c2 = apply_suggestion(AS_IS.read_text(), ["C2", "C4"], preset())
    variant = simulate_summary(c2["xml"], c2["params"], n_cases=40, seed=3, replications=3)

    comparison = compare(as_is, variant)

    qc = next(row for row in comparison["lanes"] if row["lane_id"] == "Lane_QualityControl")
    assert qc["before"] == next(r for r in as_is["lanes"] if r["lane_id"] == "Lane_QualityControl")["utilisation"]
    assert qc["after"] == next(r for r in variant["lanes"] if r["lane_id"] == "Lane_QualityControl")["utilisation"]
    assert (qc["capacity_before"], qc["capacity_after"]) == (8, 9)
    activities = {row["activity_id"]: row for row in comparison["activities"]}
    # C2 adds a retest, which only the variant has; every task of either run is listed once.
    assert activities["Task_RetestFixedDefects"]["before"] is None
    assert activities["Task_RetestFixedDefects"]["after"] is not None
    assert set(activities) == {r["activity_id"] for r in as_is["waiting_by_activity"] + variant["waiting_by_activity"]}


@pytest.mark.parametrize(
    ("setting", "other"),
    [("seed", {"seed": 8}), ("replications", {"replications": 3}), ("n_cases", {"n_cases": 30})],
)
def test_compare_refuses_runs_that_do_not_share_their_settings(setting, other):
    # Pairing replication r of both runs only means something under the same seeds and case count (common random numbers).
    run = {"n_cases": 20, "seed": 7, "replications": 2}
    baseline = simulate_summary(*as_is_preset(), **run)
    variant = simulate_summary(*as_is_preset(), **(run | other))

    with pytest.raises(ValueError, match=setting):
        compare(baseline, variant)


def test_a_run_says_which_of_its_settings_a_comparison_pairs_on():
    # The page warns before a run that won't compare with the pinned baseline, from the same list compare checks.
    summary = simulate_summary(*as_is_preset(), n_cases=20, seed=7, replications=2)

    assert summary["paired_on"] == ["seed", "replications", "n_cases"]
    assert {key: summary[key] for key in summary["paired_on"]} == {"seed": 7, "replications": 2, "n_cases": 20}


def test_the_default_arrival_rate_of_a_new_model_is_the_documented_one():
    # Pins the pilot run's number, so moving the work-per-case formula can't change it unnoticed.
    params = default_parameters((FIXTURES / "proposal_rejected.bpmn").read_text())["params"]

    assert (params["arrivals"]["rate"], params["warm_up"]["length"]) == (0.167, 599)


STUDIO = ROOT / "web" / "studio"
REBUILD = "rebuild with: uv run python scripts/build_studio.py"


def _source_files() -> dict[str, bytes]:
    """What the wheel must hold: every file of src/bpmopt/ that hatchling packs (it skips git-ignored files)."""
    src = ROOT / "src"
    return {
        path.relative_to(src).as_posix(): path.read_bytes()
        for path in sorted((src / "bpmopt").rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts and path.name != ".DS_Store"
    }


def test_the_committed_wheel_holds_the_current_package_source():
    # The browser installs this wheel, so a stale one would run old code there.
    (wheel,) = STUDIO.glob("bpmopt-*-py3-none-any.whl")
    with zipfile.ZipFile(wheel) as zf:
        packed = {name: zf.read(name) for name in zf.namelist() if name.startswith("bpmopt/")}

    source = _source_files()

    assert sorted(packed) == sorted(source), REBUILD
    stale = [name for name in source if packed[name] != source[name]]
    assert stale == [], f"stale in the wheel: {stale}; {REBUILD}"
    # micropip needs the real wheel file name, and the worker names it.
    assert wheel.name in (STUDIO / "worker.mjs").read_text(encoding="utf-8")


def test_the_studio_presets_are_the_models_files_the_suggestions_need():
    # The as-is model and parameters, the change catalog and every model file it names.
    worker = (STUDIO / "worker.mjs").read_text(encoding="utf-8")
    catalog = tomllib.loads((ROOT / "models" / "to_be.catalog.toml").read_text())
    assert set(PRESET_FILES) == {"as_is.bpmn", "as_is.params.toml", "to_be.catalog.toml", *catalog["models"].values()}

    assert sorted(p.name for p in (STUDIO / "presets").iterdir()) == sorted(PRESET_FILES), REBUILD
    for name in PRESET_FILES:
        assert (STUDIO / "presets" / name).read_bytes() == (ROOT / "models" / name).read_bytes(), f"{name}: {REBUILD}"
        assert f'"{name}"' in worker, f"the worker doesn't fetch {name}"


def test_the_studio_text_is_the_content_file():
    content = tomllib.loads((ROOT / "src" / "bpmopt" / "content" / "studio.en.toml").read_text(encoding="utf-8"))

    assert json.loads((STUDIO / "studio.en.json").read_text(encoding="utf-8")) == content, REBUILD


def test_the_studio_uses_exactly_the_labels_of_its_content_file():
    # All studio wording comes from the content file: t("key") in the page, and the
    # loading stages the worker reports, which the page shows as labels. The page's UI
    # modules (*.mjs next to it, e.g. lint-panel.mjs) count as the page.
    page = "\n".join(p.read_text(encoding="utf-8") for p in [STUDIO / "index.html", *sorted(STUDIO.glob("*.mjs"))])
    worker = (STUDIO / "worker.mjs").read_text(encoding="utf-8")
    used = set(re.findall(r"""\bt\(["'](\w+)["']""", page)) | set(re.findall(r"""\bloading\(["'](\w+)["']""", worker))
    content = tomllib.loads((ROOT / "src" / "bpmopt" / "content" / "studio.en.toml").read_text(encoding="utf-8"))

    assert used == set(content["labels"])


@pytest.mark.parametrize("path", [ROOT / "web" / "results.json", ROOT / "web" / "fixtures" / "fake_results.json"], ids=lambda p: p.name)
def test_the_report_text_in_a_results_file_is_the_content_file(path):
    # studio_try went into both files by hand; a later hand edit must not drift from page.en.toml.
    assert json.loads(path.read_text(encoding="utf-8"))["text"] == load_page_text()


def test_the_report_page_and_the_studio_link_to_each_other():
    report = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    studio = (STUDIO / "index.html").read_text(encoding="utf-8")

    assert re.search(r"""href:?=?\s*["']studio/["']""", report)
    assert re.search(r"""href=["']\.\./["']""", studio)


def test_the_reports_evaluation_section_sends_the_reader_to_the_studio_with_its_settings():
    # The lecturer reads the saving in the evaluation, then checks it in the studio.
    report = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    evaluation = report[report.index("function evaluationSection"):]
    evaluation = evaluation[: evaluation.index("\n    function ", 1)]
    labels = tomllib.loads((ROOT / "src" / "bpmopt" / "content" / "page.en.toml").read_text(encoding="utf-8"))["labels"]

    assert re.search(r"""href:\s*["']studio/["']""", evaluation)
    assert 't("studio_try"' in evaluation
    assert {"cases", "replications", "seed"} <= set(re.findall(r"\{(\w+)\}", labels["studio_try"]))
