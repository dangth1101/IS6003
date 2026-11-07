import json
import re
import tomllib
from pathlib import Path

import jsonschema
import pytest

from bpmopt.bpmn import read_bpmn
from bpmopt.parameters import assumptions, load_parameters
from bpmopt.results import build_results, element_names, export_results, validate_results
from bpmopt.scenarios import load_catalog, run_scenarios
from bpmopt.simulation import simulate


@pytest.fixture
def exported(tmp_path, simulate_fixture, fixtures_dir):
    log = simulate_fixture("sequence", n_cases=10, seed=3)
    params = load_parameters(fixtures_dir / "sequence.params.toml")
    results = build_results(log=log, model=read_bpmn(fixtures_dir / "sequence.bpmn"), params=params, seed=3)
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

    results = build_results(log=log, model=read_bpmn(fixtures_dir / "single_task.bpmn"), params=params, seed=1)

    assert results["meta"]["warm_up"] == 50.0


def test_assumptions_table_lists_every_parameter_with_its_rationale(tmp_path, simulate_fixture, fixtures_dir):
    log = simulate_fixture("rework_with_activity", n_cases=10, seed=3, params="rework_with_activity.logistic")
    params = load_parameters(fixtures_dir / "rework_with_activity.logistic.params.toml")
    results = build_results(log=log, model=read_bpmn(fixtures_dir / "rework_with_activity.bpmn"), params=params, seed=3)
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

    rows = {row["parameter"]: row["value"] for row in assumptions(params)}

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

    rows = {row["parameter"]: row["value"] for row in assumptions(params)}

    assert rows["tasks.Task_BuildApp.duration"] == "4 × (1 + 0.5 × complexity + 1 × [project_type = mobile])"


def test_exported_results_carry_the_page_text(exported):
    assert exported["text"]["lang"] == "en"
    assert exported["text"]["sections"]["problem"]["paragraphs"]


def test_export_copies_the_model_next_to_the_results(exported, tmp_path, fixtures_dir):
    copied = tmp_path / exported["models"]["as_is"]["bpmn"]
    assert copied.read_bytes() == (fixtures_dir / "sequence.bpmn").read_bytes()


def test_export_lints_each_model(exported, tmp_path, simulate_fixture, fixtures_dir):
    # A clean model gets an empty list ("checked, clean"), not a missing one ("not checked").
    assert exported["models"]["as_is"]["lint"] == []

    log = simulate_fixture("sequence", n_cases=10, seed=3)
    params = load_parameters(fixtures_dir / "sequence.params.toml")
    results = build_results(log=log, model=read_bpmn(fixtures_dir / "sequence.bpmn"), params=params, seed=3)
    path = export_results(
        results,
        tmp_path / "with_violations",
        models={"as_is": fixtures_dir / "sequence.bpmn", "to_be": fixtures_dir / "lint/event_labels.bpmn"},
    )

    lint = json.loads(path.read_text())["models"]["to_be"]["lint"]
    assert {(v["rule"], v["element_id"]) for v in lint} == {
        ("EVENT-LABEL", "Start_Unlabeled"),
        ("EVENT-LABEL", "End_Generic"),
        ("EVENT-LABEL", "End_NoObject"),
    }
    assert all(v["severity"] == "error" and v["message"] for v in lint)


def test_export_names_each_element_and_an_unnamed_xor_split_after_the_task_before_it(tmp_path, simulate_fixture, fixtures_dir):
    # The page and the notebook both label tables with these names, so the rule lives in one place.
    model = read_bpmn(fixtures_dir / "rework_with_activity.bpmn")
    log = simulate_fixture("rework_with_activity", n_cases=10, seed=3)
    params = load_parameters(fixtures_dir / "rework_with_activity.params.toml")
    results = build_results(log=log, model=model, params=params, seed=3)

    path = export_results(results, tmp_path, models={"as_is": fixtures_dir / "rework_with_activity.bpmn"})

    names = json.loads(path.read_text())["models"]["as_is"]["names"]
    assert names == element_names(model)
    assert names["Task_TestBuild"] == "Test build"
    assert names["Flow_Failed"] == "tests failed"
    assert names["Gateway_LoopSplit"] == "Decision after Test build"
    # The loop's XOR-join has two incoming flows, so no single element comes before it.
    assert "Gateway_LoopJoin" not in names


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


def _prose(content: dict) -> list[str]:
    """Section paragraphs and threats: the page text that may carry {name} placeholders filled from the results."""
    paragraphs = [p for section in content["sections"].values() for p in section["paragraphs"]]
    return paragraphs + [part for threat in content["threats"] for part in (threat["title"], threat["detail"])]


def _prose_names(results: dict) -> set[str]:
    """The placeholder names the page fills for these results (index.html, proseVars), as the content file's header lists them."""
    ids = [change["id"] for change in results["changes"]]
    keys = ["_".join(i for i in ids if i in s["changes"]) for s in results["scenarios"] if s["changes"]] + ["full", "best"]
    names = {"replications", "change_count", "scenario_count", "best_changes"}
    names |= {f"{name}_{key}" for key in keys for name in ("share", "saving")} | {f"share_{key}_ci" for key in keys}
    names |= {f"alone_{i}" for i in ids} | {f"full_minus_{i}{suffix}" for i in ids for suffix in ("", "_abs", "_ci")}
    return names | {f"rework_{r['gateway_id']}" for r in results["baseline"]["rework"]}


PAGE_CONTENT = Path(__file__).parents[1] / "src/bpmopt/content/page.en.toml"


def test_every_placeholder_in_the_page_prose_names_a_result_the_page_fills():
    # A placeholder the page can't fill would show as "{name}" on screen.
    content = tomllib.loads(PAGE_CONTENT.read_text(encoding="utf-8"))
    results = json.loads((WEB / "results.json").read_text(encoding="utf-8"))

    used = {name for text in _prose(content) for name in re.findall(r"\{(\w+)\}", text)}

    assert used
    assert used <= _prose_names(results)


def test_the_page_prose_types_in_no_result():
    # Results come from results.json through placeholders, so a rerun can't leave
    # stale numbers in the text. What may stay: book citations, change and guideline
    # IDs, the 95% confidence level, the 20% objective, the 30-element limit of G7,
    # the year of the method paper and the names graph2vec and node2vec.
    allowed = [
        r"§[\d.]+", r"\bpp?\.[\d-]+", r"\b(?:Appendix|Eq\.|Fig\.|Table) [A-Z]?[\d.]*\d", r"\b[CG]\d\b",
        r"\b95%", r"\b20%", r"\b30[- ]elements?", r"\b7PMG", r"Peffers et al\., 2007", r"\b2nd ed\.",
        r"\b(?:[Gg]raph|[Nn]ode)2vec\b",
    ]
    content = tomllib.loads(PAGE_CONTENT.read_text(encoding="utf-8"))

    for text in _prose(content):
        stripped = re.sub("|".join(allowed), "", re.sub(r"\{\w+\}", "", text))
        assert not re.search(r"\d", stripped), f"a number is typed into the page text: {text!r}"


def test_fake_results_fill_every_section_of_the_spec(fake):
    # Spec, "Results contract", plus `text` for the page wording and the ablation and headline derived from the scenarios.
    spec_sections = {"meta", "assumptions", "models", "value_added", "baseline", "ml", "clusters", "changes", "scenarios", "threats"}

    assert set(fake) == spec_sections | {"text", "ablation", "headline"}
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


BASELINE_FIELDS = {
    "time_unit",
    "cycle_time",
    "processing_time",
    "waiting_time",
    "cycle_time_efficiency",
    "rework",
    "waiting_by_activity",
    "flow_analysis",
    "by_outcome",
}


def test_exported_baseline_has_every_measure(tmp_path, simulate_fixture, fixtures_dir):
    log = simulate_fixture("proposal_rejected", n_cases=300, seed=3)
    model = read_bpmn(fixtures_dir / "proposal_rejected.bpmn")
    params = load_parameters(fixtures_dir / "proposal_rejected.params.toml")

    results = build_results(log=log, model=model, params=params, seed=3)
    path = export_results(results, tmp_path, models={"as_is": fixtures_dir / "proposal_rejected.bpmn"})

    baseline = json.loads(path.read_text())["baseline"]
    assert set(baseline) == BASELINE_FIELDS
    assert baseline["flow_analysis"]["theoretical"] == pytest.approx(8.4)  # worked by hand in the params file
    assert {row["gateway_id"] for row in baseline["rework"]} == {"Gateway_ReviewSplit", "Gateway_TestSplit"}
    assert {row["end_event_id"] for row in baseline["by_outcome"]} == {"End_AppReleased", "End_ProposalRejected"}


@pytest.mark.parametrize("field", sorted(BASELINE_FIELDS))
def test_a_baseline_missing_any_measure_is_rejected(exported, field):
    del exported["baseline"][field]

    with pytest.raises(jsonschema.ValidationError):
        validate_results(exported)


def _fitted_task(fake, kind):
    return next(t for t in fake["ml"]["tasks"] if t["kind"] == kind and "skipped" not in t)


@pytest.mark.parametrize("kind", ["regression", "classification"])
def test_an_ml_task_without_its_reference_model_is_rejected(fake, kind):
    task = _fitted_task(fake, kind)
    task["models"] = [m for m in task["models"] if m["id"] != "reference"]

    with pytest.raises(jsonschema.ValidationError):
        validate_results(fake)


@pytest.mark.parametrize(
    ("kind", "metrics"),
    [
        ("regression", {"roc_auc": 0.7, "f1": 0.5}),
        ("regression", {"mae": 10.0}),
        ("classification", {"mae": 10.0, "r2": 0.2}),
        ("classification", {"roc_auc": 0.7, "f1": 0.5, "r2": 0.2}),
    ],
)
def test_ml_metrics_must_match_the_task_kind(fake, kind, metrics):
    _fitted_task(fake, kind)["models"][0]["metrics"] = metrics

    with pytest.raises(jsonschema.ValidationError):
        validate_results(fake)


def test_a_lint_violation_names_an_element_even_for_model_level_rules(fake):
    # Model-level rules (POOL, G7) name the process ID, never null.
    fake["models"]["as_is"]["lint"] = [{"rule": "G7", "element_id": None, "severity": "warning", "message": "Too big."}]

    with pytest.raises(jsonschema.ValidationError):
        validate_results(fake)


def test_results_report_the_replications_the_scenarios_ran_with(simulate_fixture, fixtures_dir):
    log = simulate_fixture("sequence", n_cases=10, seed=3)
    params = load_parameters(fixtures_dir / "sequence.params.toml")

    results = build_results(log=log, model=read_bpmn(fixtures_dir / "sequence.bpmn"), params=params, seed=3, replications=30)

    assert results["meta"]["replications"] == 30


def test_threats_to_validity_come_from_the_page_content_file(exported):
    # Threats are page text, so a translation edits the content file, not the notebook.
    content = tomllib.loads((Path(__file__).parents[1] / "src/bpmopt/content/page.en.toml").read_text(encoding="utf-8"))

    assert exported["threats"] == content["threats"]
    assert "threats" not in exported["text"]


SCENARIO_PARAMS = "sequence.scenarios.params.toml"


@pytest.fixture
def with_scenarios(fixtures_dir):
    """Results with the fixture catalog's full factorial, 3 replications, built the way the notebook does it."""
    model = read_bpmn(fixtures_dir / "sequence.bpmn")
    params = load_parameters(fixtures_dir / SCENARIO_PARAMS)
    catalog = load_catalog(fixtures_dir / "sequence.catalog.toml", model=model, params=params)
    log = simulate(model, params, n_cases=30, seed=5)
    scenarios = run_scenarios(catalog, n_cases=30, replications=3, seed=5)
    results = build_results(log=log, model=model, params=params, seed=5, catalog=catalog, scenarios=scenarios)
    return results | {"models": {"as_is": {"bpmn": "models/as_is.bpmn", "names": element_names(model)}}}


def test_results_with_scenarios_an_ablation_and_a_headline_validate(with_scenarios):
    validate_results(with_scenarios)


def test_results_with_scenarios_carry_the_catalog_the_ablation_and_the_headline(with_scenarios):
    # Fixture catalog: C1 and C2 each shorten every case, C3 adds a developer.
    assert [change["id"] for change in with_scenarios["changes"]] == ["C1", "C2", "C3"]
    assert len(with_scenarios["scenarios"]) == 2**3
    assert [row["change"] for row in with_scenarios["ablation"]] == ["C1", "C2", "C3"]
    assert with_scenarios["headline"]["changes"] == ["C1", "C2", "C3"]
    assert with_scenarios["meta"]["replications"] == 3


def test_the_assumptions_list_every_override_of_the_redesign_marked_with_its_change(with_scenarios, fixtures_dir):
    # Every parameter goes in the assumptions table, the to-be ones too. The as-is
    # rows come first and carry no change; then each change's overrides, in catalog order.
    as_is = assumptions(load_parameters(fixtures_dir / SCENARIO_PARAMS))
    rows = with_scenarios["assumptions"]

    assert rows[: len(as_is)] == as_is
    assert rows[len(as_is) :] == [
        {"parameter": "tasks.Task_BuildApp.duration", "value": "triangular(1, 3, 8)", "rationale": "The as-is duration shifted down by 2 days.", "change": "C1"},
        {"parameter": "lanes.Lane_Dev.capacity", "value": 3, "rationale": "One developer more than the as-is team.", "change": "C3"},
    ]


def test_an_assumption_marked_with_a_change_must_name_one_in_the_catalog(with_scenarios):
    with_scenarios["assumptions"][-1]["change"] = "C9"

    with pytest.raises(jsonschema.ValidationError, match="C9"):
        validate_results(with_scenarios)


def test_the_saving_share_must_be_the_saving_over_the_as_is_mean(with_scenarios):
    # The headline shows the share next to the days, so the two must agree.
    with_scenarios["scenarios"][3]["saving_share"] = {"value": 0.5, "ci_low": 0.4, "ci_high": 0.6}

    with pytest.raises(jsonschema.ValidationError, match="saving_share"):
        validate_results(with_scenarios)


def test_the_ablation_must_agree_with_the_scenarios(with_scenarios):
    # The page reads the ablation as written, so a stale one would show wrong numbers.
    with_scenarios["ablation"][0]["full_minus"]["value"] += 1.0
    with_scenarios["ablation"][0]["full_minus"]["ci_high"] += 1.0

    with pytest.raises(jsonschema.ValidationError, match="ablation"):
        validate_results(with_scenarios)


@pytest.mark.parametrize(("field", "value"), [("changes", ["C1", "C9"]), ("best", ["C9"]), ("top_change", "C9")])
def test_the_headline_must_name_scenarios_and_changes_that_exist(with_scenarios, field, value):
    with_scenarios["headline"][field] = value

    with pytest.raises(jsonschema.ValidationError, match="headline"):
        validate_results(with_scenarios)


def test_every_scenario_needs_one_mean_per_replication(with_scenarios):
    with_scenarios["meta"]["replications"] = 30

    with pytest.raises(jsonschema.ValidationError, match="replication_means"):
        validate_results(with_scenarios)


def test_the_replication_means_must_average_to_the_mean_estimate(with_scenarios):
    with_scenarios["scenarios"][2]["replication_means"][0] += 5.0

    with pytest.raises(jsonschema.ValidationError, match="replication_means"):
        validate_results(with_scenarios)
