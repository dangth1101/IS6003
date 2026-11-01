"""Assemble, validate and export the results file the static page reads.

The JSON schema in schema/results.schema.json is the contract between the
notebook and the page. Every export is validated against it.
"""

import json
import shutil
import tomllib
from collections import Counter
from collections.abc import Iterator
from dataclasses import asdict
from datetime import UTC, datetime
from functools import cache
from importlib import resources
from itertools import combinations
from pathlib import Path

import jsonschema
import pandas as pd

from bpmopt.analysis import baseline_metrics, flow_analysis_check
from bpmopt.bpmn import ProcessModel, read_bpmn
from bpmopt.lint import lint
from bpmopt.parameters import Parameters, assumptions

SCHEMA_VERSION = 2


def build_results(*, log: pd.DataFrame, model: ProcessModel, params: Parameters, seed: int, lang: str = "en") -> dict:
    """Results without the `models` section, which export_results fills in.

    `log` is the simulation of `model` with `params` and `seed`. The flow
    analysis check simulates the model once more with unlimited capacity, with
    the same seed and case count.

    The notebook adds the other sections (value_added, ml, changes,
    scenarios, threats) to this dict before export.
    """
    return {
        "meta": {
            "schema_version": SCHEMA_VERSION,
            "seed": seed,
            "replications": 1,  # one baseline run; run_scenarios runs R replications per scenario
            "case_count": int(log.case_id.nunique()),
            "warm_up": params.warm_up,
            "parameter_version": params.version,
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        },
        "text": load_page_text(lang),
        "assumptions": assumptions(params),
        "baseline": {
            "time_unit": "working days",
            **baseline_metrics(log, model),
            "flow_analysis": flow_analysis_check(model, params, n_cases=int(log.case_id.nunique()), seed=seed),
        },
    }


def load_page_text(lang: str = "en") -> dict:
    """Page text from content/page.<lang>.toml. Translating the page means adding a file there."""
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
    are the full factorial of the change catalog, and every CI holds its estimate.
    """
    error = jsonschema.exceptions.best_match(_validator().iter_errors(results))
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

    for i, scenario in enumerate(scenarios):
        estimates = {f"cycle_time.{k}": v for k, v in scenario["cycle_time"].items()} | {"saving": scenario["saving"]}
        for name, e in estimates.items():
            if not e["ci_low"] <= e["value"] <= e["ci_high"]:
                yield f"scenarios[{i}].{name}: interval [{e['ci_low']}, {e['ci_high']}] doesn't contain {e['value']}"


def validate_changes(changes: list[dict]) -> None:
    """Raise jsonschema.ValidationError if a change catalog breaks the contract's `changes` section.

    Lets the catalog loader catch a bad entry before any simulation runs.
    """
    validator = _validator()
    section = validator.schema["properties"]["changes"]
    error = jsonschema.exceptions.best_match(validator.evolve(schema={**section, "$defs": validator.schema["$defs"]}).iter_errors(changes))
    if error is not None:
        raise error


@cache
def _validator() -> jsonschema.Draft202012Validator:
    schema = json.loads(resources.files("bpmopt").joinpath("schema/results.schema.json").read_text())
    # Formats like date-time are only checked with a format checker (needs rfc3339-validator).
    return jsonschema.Draft202012Validator(schema, format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER)
