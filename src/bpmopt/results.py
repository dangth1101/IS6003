"""Assemble, validate and export the results file the static page reads.

The JSON schema in schema/results.schema.json is the contract between the
notebook and the page. Every export is validated against it.
"""

import json
import math
import shutil
import tomllib
from collections import Counter
from collections.abc import Iterator
from dataclasses import asdict
from datetime import UTC, datetime
from importlib import resources
from itertools import combinations
from pathlib import Path

import jsonschema
import pandas as pd

from bpmopt.analysis import baseline_metrics, flow_analysis_check
from bpmopt.bpmn import ProcessModel, read_bpmn
from bpmopt.contract import validator
from bpmopt.lint import lint
from bpmopt.parameters import Parameters, assumptions
from bpmopt.scenarios import Catalog, ablation, find_scenario, headline, saving_share

SCHEMA_VERSION = 6


def build_results(
    *,
    log: pd.DataFrame,
    model: ProcessModel,
    params: Parameters,
    seed: int,
    replications: int | None = None,
    value_added: dict | None = None,
    ml: dict | None = None,
    clusters: dict | None = None,
    social: dict | None = None,
    catalog: Catalog | None = None,
    scenarios: list[dict] | None = None,
    lang: str = "en",
) -> dict:
    """Results without the `models` section, which export_results fills in.

    `log` is the simulation of `model` with `params` and `seed`. The flow
    analysis check simulates the model once more with unlimited capacity, with
    the same seed and case count. Every cycle time stops at the parameters'
    cut-off (cycle_time_end), if they set one.

    The optional sections go in as given: value_added (load_value_added), ml
    (ml_section), clusters (clusters_section), social (social_section), the change catalog and the scenarios run_scenarios returned
    for it. With scenarios, the ablation and the headline are derived from them
    and `replications` defaults to the runs per scenario (else 1). The catalog's
    overrides join the assumptions table after the as-is rows, each marked with
    its change. The threats to validity come from the page content file, like
    the page text.
    """
    if scenarios is not None and catalog is None:
        raise ValueError("scenarios need the catalog they were run from")
    if replications is None:
        replications = len(scenarios[0]["replication_means"]) if scenarios else 1
    results = {
        "meta": {
            "schema_version": SCHEMA_VERSION,
            "seed": seed,
            "replications": replications,
            "case_count": int(log.case_id.nunique()),
            "warm_up": params.warm_up,
            "parameter_version": params.version,
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        },
        "text": load_page_text(lang),
        "assumptions": assumptions(params) + (catalog.assumptions() if catalog else []),
        "threats": _page_content(lang)["threats"],
        "baseline": {
            "time_unit": "working days",
            **baseline_metrics(log, model, ends_at=params.cycle_time_end),
            "flow_analysis": flow_analysis_check(model, params, n_cases=int(log.case_id.nunique()), seed=seed),
        },
    }
    if value_added is not None:
        results["value_added"] = value_added
    if ml is not None:
        results["ml"] = ml
    if clusters is not None:
        results["clusters"] = clusters
    if social is not None:
        results["social"] = social
    if catalog is not None:
        results["changes"] = catalog.entries()
    if scenarios is not None:
        rows = ablation(scenarios)
        results |= {"scenarios": scenarios, "ablation": rows, "headline": headline(scenarios, rows)}
    return results


def load_page_text(lang: str = "en") -> dict:
    """Page text from content/page.<lang>.toml, without the threats. Translating the page means adding a file there."""
    return {key: value for key, value in _page_content(lang).items() if key != "threats"}


def _page_content(lang: str) -> dict:
    source = resources.files("bpmopt").joinpath(f"content/page.{lang}.toml")
    return tomllib.loads(source.read_text(encoding="utf-8"))


def export_results(results: dict, out_dir: str | Path, *, models: dict[str, Path]) -> Path:
    """Copy each BPMN model into out_dir/models/, lint it, and write out_dir/results.json.

    out_dir ends up self-contained, so it can be served as a static site. Each
    model's lint list is empty when it is clean. Each model also carries its
    element names (see element_names), so the page labels tables the same way
    the notebook does.
    """
    out_dir = Path(out_dir)
    (out_dir / "models").mkdir(parents=True, exist_ok=True)
    results = {**results, "models": {}}
    for key, source in models.items():
        target = Path("models") / f"{key}.bpmn"
        shutil.copyfile(source, out_dir / target)
        results["models"][key] = {
            "bpmn": target.as_posix(),
            "names": element_names(read_bpmn(source), results["text"]),
            "lint": [asdict(v) for v in lint(source)],
        }

    validate_results(results)
    path = out_dir / "results.json"
    path.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def element_names(model: ProcessModel, text: dict | None = None) -> dict[str, str]:
    """Element ID -> display name, for every named node, flow and lane of the model.

    Gateways in the models are unnamed. An unnamed XOR gateway with one
    incoming flow is named after the element before it, with the page text's
    `gateway_after` label ("Decision after {task}"). text defaults to the
    English page text.
    """
    gateway_after = (text or load_page_text())["labels"]["gateway_after"]
    names = {lane_id: name for lane_id, name in model.lanes.items() if name}
    names |= {flow.id: flow.label for flow in model.flows.values() if flow.label}
    names |= {node.id: node.label for node in model.nodes.values() if node.label}
    for gateway in model.nodes_of_type("exclusiveGateway"):
        incoming = model.incoming(gateway.id)
        if gateway.id not in names and len(incoming) == 1 and incoming[0].source in names:
            names[gateway.id] = gateway_after.replace("{task}", names[incoming[0].source])
    return names


def validate_results(results: dict) -> None:
    """Raise jsonschema.ValidationError if results break the contract.

    First the JSON schema, then the rules a schema can't express: the scenarios
    are the full factorial of the change catalog, every CI holds its estimate,
    each scenario has one mean per replication that average to its estimate,
    every saving share is its saving over the as-is mean, assumptions marked
    with a change name one in the catalog, the ablation and the headline
    match the scenarios, and the groups match their points.
    """
    error = jsonschema.exceptions.best_match(validator().iter_errors(results))
    if error is not None:
        raise error
    for message in _cross_field_errors(results):
        raise jsonschema.ValidationError(message)


def _cross_field_errors(results: dict) -> Iterator[str]:
    scenarios = results.get("scenarios", [])
    if scenarios:
        catalog = [change["id"] for change in results.get("changes", [])]
        seen = Counter(frozenset(s["changes"]) for s in scenarios)
        unknown = set().union(*seen) - set(catalog)
        if unknown:
            yield f"scenarios use changes that aren't in the catalog: {', '.join(sorted(unknown))}"
        for k in range(len(catalog) + 1):
            for combo in combinations(catalog, k):
                if seen[frozenset(combo)] != 1:
                    count = seen[frozenset(combo)]
                    yield f"expected one scenario for changes [{', '.join(combo)}], found {count}"

    catalog_ids = {change["id"] for change in results.get("changes", [])}
    for i, row in enumerate(results.get("assumptions", [])):
        if "change" in row and row["change"] not in catalog_ids:
            yield f"assumptions[{i}] ({row['parameter']}): change {row['change']} isn't in the change catalog"

    replications = results["meta"]["replications"]
    as_is = find_scenario(scenarios, [])
    for i, scenario in enumerate(scenarios):
        estimates = {f"cycle_time.{k}": v for k, v in scenario["cycle_time"].items()}
        estimates |= {"saving": scenario["saving"], "saving_share": scenario["saving_share"]}
        for name, e in estimates.items():
            if not e["ci_low"] <= e["value"] <= e["ci_high"]:
                yield f"scenarios[{i}].{name}: interval [{e['ci_low']}, {e['ci_high']}] doesn't contain {e['value']}"
        runs = scenario["replication_means"]
        if len(runs) != replications:
            yield f"scenarios[{i}].replication_means: {len(runs)} values, but meta.replications is {replications}"
        elif not _close(sum(runs) / len(runs), scenario["cycle_time"]["mean"]["value"]):
            yield f"scenarios[{i}].replication_means: their average isn't cycle_time.mean.value"
        if as_is is not None:
            want = saving_share(scenario["saving"], as_is["cycle_time"]["mean"]["value"])
            if not all(_close(scenario["saving_share"][k], want[k]) for k in want):
                yield f"scenarios[{i}].saving_share: must be the saving and its CI divided by the as-is mean cycle time, expected {want}"

    yield from _summary_errors(results, scenarios)
    yield from _cluster_errors(results)
    if "social" in results:
        lanes = {e[k] for e in results["social"]["handovers"] for k in ("source", "target")}
        scored = {row["lane_id"] for row in results["social"]["centrality"]}
        if scored != lanes:
            yield f"social.centrality: lanes {sorted(scored ^ lanes)} are in only one of handovers and centrality"
        for row in results["social"]["centrality"]:
            got = sum(e["count"] for e in results["social"]["handovers"] if e["target"] == row["lane_id"])
            gave = sum(e["count"] for e in results["social"]["handovers"] if e["source"] == row["lane_id"])
            if (row["in_handovers"], row["out_handovers"]) != (got, gave):
                yield f"social.centrality ({row['lane_id']}): in and out handovers must add up the handovers, expected {got} and {gave}"


def _cluster_errors(results: dict) -> Iterator[str]:
    """Each grouping has groups 0..k-1, k is one it tried, and its groups agree with its points."""
    clusters = results.get("clusters")
    if clusters is None:
        return
    for name, size_of in (("cases", lambda g: g["case_count"]), ("activities", lambda g: len(g["activity_ids"]))):
        section = clusters[name]
        k = section["k"]
        if [g["id"] for g in section["groups"]] != list(range(k)):
            yield f"clusters.{name}.groups: expected ids 0 to {k - 1} in order"
        if k not in {row["k"] for row in section["silhouette"]}:
            yield f"clusters.{name}.k: {k} isn't one of the k in silhouette"
        sizes = Counter(point["group"] for point in section["points"])
        for g in section["groups"]:
            if sizes[g["id"]] != size_of(g):
                yield f"clusters.{name}.groups[{g['id']}]: {size_of(g)} members, but {sizes[g['id']]} points"
        if set(sizes) - set(range(k)):
            yield f"clusters.{name}.points: groups {sorted(set(sizes) - set(range(k)))} don't exist"
    if len(clusters["cases"]["points"]) != results["meta"]["case_count"]:
        yield f"clusters.cases.points: {len(clusters['cases']['points'])} cases, but meta.case_count is {results['meta']['case_count']}"
    by_activity = {p["activity_id"]: p["group"] for p in clusters["activities"]["points"]}
    for g in clusters["activities"]["groups"]:
        wrong = [a for a in g["activity_ids"] if by_activity.get(a) != g["id"]]
        if wrong:
            yield f"clusters.activities.groups[{g['id']}]: {', '.join(wrong)} aren't in that group in points"


def _summary_errors(results: dict, scenarios: list[dict]) -> Iterator[str]:
    """The ablation and the headline are derived from the scenarios, so they must match them."""
    if ("ablation" in results or "headline" in results) and not scenarios:
        yield "ablation and headline need scenarios"
        return
    if "ablation" in results:
        expected = ablation(scenarios)
        for i, (row, want) in enumerate(zip(results["ablation"], expected, strict=False)):
            same = row["change"] == want["change"] and all(
                _close(row[view][k], want[view][k]) for view in ("alone", "full_minus") for k in ("value", "ci_low", "ci_high")
            )
            if not same:
                yield f"ablation[{i}] doesn't match the scenarios: expected {want}"
        if len(results["ablation"]) != len(expected):
            yield f"ablation has {len(results['ablation'])} rows, expected one per change ({len(expected)})"
    if "headline" in results:
        summary = results["headline"]
        catalog = {change["id"] for change in results.get("changes", [])}
        for field in ("changes", "best"):
            if find_scenario(scenarios, summary[field]) is None:
                yield f"headline.{field}: no scenario has changes [{', '.join(summary[field])}]"
        if summary["top_change"] not in catalog:
            yield f"headline.top_change: {summary['top_change']} isn't in the change catalog"


def _close(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)
