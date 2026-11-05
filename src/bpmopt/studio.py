"""The studio's Python seam: what the studio page calls in the browser (Pyodide).

Everything here is JSON in, JSON out: BPMN as an XML string, parameters as the
parameter file's tables in a dict (see bpmopt.parameters), results as dicts
of floats and lists. No file paths, so the page never needs a file system.

Simulation goes through the same simulate + replication seeds as the scenario
runner, so the studio and the notebook give the same numbers for the same
model, parameters, cases, replications and seed.

Suggestions (apply_suggestion, suggestions) work on the as-is preset: the
preset files, models/as_is.* and the change catalog models/to_be.catalog.toml
with its model files, passed in as `preset`, a dict of file name -> text (the
worker fetches them from web/studio/presets/).

Only the simulation path may be imported from here: no ml, features, results
or planted, which pull in scikit-learn and SHAP or aren't needed in the browser.
"""

import copy
import json
import tomllib
from collections.abc import Callable, Mapping
from dataclasses import replace
from xml.etree import ElementTree

import numpy as np

from bpmopt.analysis import baseline_metrics, utilisation
from bpmopt.bpmn import ProcessModel, parse_bpmn
from bpmopt.lint import ERROR, lint_model
from bpmopt.parameters import Logistic, parse_parameters
from bpmopt.scenarios import Catalog, estimate, parse_catalog, replication_seeds, saving_share
from bpmopt.simulation import simulate

PRESET_MODEL = "as_is.bpmn"
PRESET_PARAMS = "as_is.params.toml"
PRESET_CATALOG = "to_be.catalog.toml"

# Defaults for a new or imported model (default_parameters). Every one is an
# assumption the page shows, so the user can replace it with an estimate.
#
# - Task duration triangular [1, 2, 4] working days: a short task of about two
#   days that sometimes takes twice that. Same shape as the shortest as-is tasks
#   (code review, plan approval), so a new task doesn't dominate the cycle time.
# - XOR split: every outgoing flow equally likely. Nothing says one branch is
#   more common, and equal shares are the easiest to see and change.
# - Lane capacity 1: one person per lane, so a lane's tasks queue for them.
#   The smallest real lane; raise it to the lane's head count.
# - Arrival rate: the rate that keeps the busiest lane 80% busy (rho = rate x
#   work per case / capacity, Eq. 7.8 p.270). Busy enough that waiting shows in
#   the results, far enough below 1 that the queues settle (p.276). The as-is
#   preset's busiest lane is at 0.87. Work per case comes from a 1,000-case pilot
#   run without queues (seed 0), so loops and parallel branches count.
#   Rounded to 3 significant digits.
# - Warm-up: the time 100 cases take to arrive (100 / rate, whole days), so the
#   queues fill from the empty start before cases are measured. Costs 10% more
#   simulation at the default 1,000 cases. Only set together with a default rate.
# - No default cycle time cut-off (cycles end at the end events) and no case
#   attributes: those only come from an imported parameter file.
#
# An entry is a default when its rationale starts with STUDIO_DEFAULT, so it
# stays marked when the page sends the parameters back, and stops being one
# once the page gives an edited entry its own rationale.
STUDIO_DEFAULT = "Studio default."
DEFAULT_VERSION = "studio-1"
DEFAULT_DURATION = [1, 2, 4]
DEFAULT_CAPACITY = 1
TARGET_UTILISATION = 0.8
WARM_UP_CASES = 100
PILOT_CASES = 1_000
PILOT_SEED = 0
_RATIONALES = {
    "tasks": "Triangular [1, 2, 4] working days, a short task of about two days. Replace it with an estimate.",
    "gateways": "Every outgoing flow equally likely, since nothing says one is more common. Replace it with an estimated share.",
    "lanes": "One resource, so the lane's tasks queue for it. Set it to the number of people or teams in the lane.",
    "arrivals": "Keeps the busiest lane, {lane}, about {target:.0%} busy (rate x work per case / capacity, Eq. 7.8): "
    "busy enough that queues show, below 1 so they settle (p.276). Work per case from a {cases:,}-case run without queues.",
    "warm_up": "The time about {cases} cases take to arrive, so the lane queues fill before cases are measured.",
}


def simulate_summary(
    xml: str,
    params: dict,
    n_cases: int,
    seed: int,
    replications: int,
    progress: Callable[[int, int], None] | None = None,
) -> dict:
    """Simulate the model `replications` times and summarise where the time goes.

    Replication r runs with replication_seeds(seed, replications)[r], like the
    scenario runner. Each replication gives the measures of the report's
    baseline section (analysis.baseline_metrics) plus the utilisation per lane;
    every number below is their mean over replications with a 95% t-interval,
    an estimate {value, ci_low, ci_high}:

    - cycle_time: {mean, median, p90}, shaped like a scenario's in the results file
    - processing_time, waiting_time: {mean}
    - cycle_time_efficiency: mean processing time / mean cycle time (§7.1.2)
    - lanes: [{lane_id, label, capacity, utilisation}] per lane with a capacity,
      in model order; empty without an arrival rate (see analysis.utilisation)
    - rework: [{gateway_id, label, rate}] per rework gateway, in model order
    - waiting_by_activity: [{activity_id, label, mean}], longest wait first

    A gateway or task that fewer than 2 replications reach has no CI and is
    left out. replication_means keeps each replication's mean cycle time, so
    two runs can be paired (see compare); n_cases, seed and replications are
    returned for the same reason. progress, if given, is called with
    (replications done, replications) after each one.
    """
    if replications < 2:
        raise ValueError(f"need at least 2 replications for a confidence interval, got {replications}")
    model = parse_bpmn(xml)
    parameters = parse_parameters(params, model)
    runs, rhos = [], []
    for r, replication_seed in enumerate(replication_seeds(seed, replications)):
        log = simulate(model, parameters, n_cases=n_cases, seed=replication_seed)
        runs.append(baseline_metrics(log, model, ends_at=parameters.cycle_time_end))
        rhos.append(utilisation(log, parameters) if parameters.arrival_rate is not None else {})
        if progress is not None:
            progress(r + 1, replications)

    def over_runs(values: list[float]) -> dict[str, float]:
        return estimate(np.array(values))

    lanes = [lane_id for lane_id in model.lanes if lane_id in parameters.lane_capacities and parameters.arrival_rate is not None]
    rework = _per_element([{row["gateway_id"]: row["rate"] for row in run["rework"]} for run in runs])
    waiting = _per_element([{row["activity_id"]: row["mean"] for row in run["waiting_by_activity"]} for run in runs])
    return {
        "n_cases": n_cases,
        "seed": seed,
        "replications": replications,
        "cycle_time": {stat: over_runs([run["cycle_time"][stat] for run in runs]) for stat in ("mean", "median", "p90")},
        "processing_time": {"mean": over_runs([run["processing_time"]["mean"] for run in runs])},
        "waiting_time": {"mean": over_runs([run["waiting_time"]["mean"] for run in runs])},
        "cycle_time_efficiency": over_runs([run["cycle_time_efficiency"] for run in runs]),
        "lanes": [
            {
                "lane_id": lane_id,
                "label": model.lanes[lane_id],
                "capacity": parameters.lane_capacities[lane_id],
                "utilisation": over_runs([rho[lane_id] for rho in rhos]),
            }
            for lane_id in lanes
        ],
        "rework": [{"gateway_id": i, "label": model.nodes[i].label, "rate": rate} for i, rate in rework.items()],
        "waiting_by_activity": sorted(
            [{"activity_id": i, "label": model.nodes[i].label, "mean": mean} for i, mean in waiting.items()],
            key=lambda row: row["mean"]["value"],
            reverse=True,
        ),
        "replication_means": [run["cycle_time"]["mean"] for run in runs],
    }


def default_parameters(xml: str, params: dict | None = None) -> dict:
    """A full parameter set for the model: {params, defaults, dropped}.

    Given entries are kept as they are. Missing tasks, XOR splits and lanes get
    the defaults above, and so do the arrival rate and warm-up when there is no
    [arrivals] (only once the model has no lint errors, since the rate needs a
    pilot run). Entries for tasks, XOR splits and lanes the model doesn't have
    are dropped, so is a cycle time cut-off at a missing task, and a branch
    table that no longer has one branch per outgoing flow is replaced by the
    default. defaults lists the entries that are defaults ("tasks.Task_X",
    "arrivals", ...), dropped the entries removed, each in parameter file order.
    """
    model = parse_bpmn(xml)
    raw = copy.deepcopy(params) if params else {}
    raw.setdefault("version", DEFAULT_VERSION)
    tasks = [node.id for node in model.nodes_of_type("task")]
    splits = {node.id: [flow.id for flow in model.outgoing(node.id)] for node in model.xor_splits()}
    known = {"tasks": set(tasks), "gateways": set(splits), "lanes": set(model.lanes)}

    dropped = []
    for section, ids in known.items():
        for element_id in list(raw.get(section, {})):
            stale = section == "gateways" and element_id in splits and set(raw[section][element_id].get("branches", {})) != set(splits[element_id])
            if element_id not in ids or stale:
                del raw[section][element_id]
                dropped.append(f"{section}.{element_id}")
    if "cycle_time" in raw and raw["cycle_time"].get("ends_at") not in known["tasks"]:
        del raw["cycle_time"]
        dropped.append("cycle_time")

    def fill(section: str, element_id: str, key: str, value) -> None:
        entries = raw.setdefault(section, {})
        if element_id not in entries:
            entries[element_id] = {key: value, "rationale": f"{STUDIO_DEFAULT} {_RATIONALES[section]}"}

    for lane_id in model.lanes:
        fill("lanes", lane_id, "capacity", DEFAULT_CAPACITY)
    for task_id in tasks:
        fill("tasks", task_id, "duration", {"triangular": list(DEFAULT_DURATION)})
    for gateway_id, flows in splits.items():
        fill("gateways", gateway_id, "branches", {flow_id: 1 / len(flows) for flow_id in flows})
    raw = {section: value for section, value in raw.items() if value != {} or section not in known}
    if "arrivals" not in raw and not any(v.severity == ERROR for v in lint_model(model)):
        _fill_arrivals(raw, model)

    entries = [(section, None) for section in ("arrivals", "warm_up", "cycle_time")] + [
        (section, element_id) for section in ("attributes", "lanes", "tasks", "gateways") for element_id in raw.get(section, {})
    ]
    defaults = [
        section if element_id is None else f"{section}.{element_id}"
        for section, element_id in entries
        if section in raw and (raw[section] if element_id is None else raw[section][element_id]).get("rationale", "").startswith(STUDIO_DEFAULT)
    ]
    return {"params": raw, "defaults": defaults, "dropped": dropped}


def _fill_arrivals(raw: dict, model: ProcessModel) -> None:
    """Set [arrivals] (and [warm_up], if missing) so the busiest limited lane runs at TARGET_UTILISATION."""
    pilot = parse_parameters({key: value for key, value in raw.items() if key != "warm_up"}, model)
    log = simulate(model, replace(pilot, lane_capacities={}), n_cases=PILOT_CASES, seed=PILOT_SEED)
    tasks = log[log.element_type == "task"]
    work = (tasks.end_time - tasks.start_time).groupby(tasks.lane_id).sum() / PILOT_CASES
    room = {lane_id: c / work[lane_id] for lane_id, c in pilot.lane_capacities.items() if work.get(lane_id, 0) > 0}
    if not room:
        return
    busiest = min(room, key=room.get)
    rate = float(f"{TARGET_UTILISATION * room[busiest]:.3g}")
    reason = _RATIONALES["arrivals"].format(lane=model.lanes[busiest] or busiest, target=TARGET_UTILISATION, cases=PILOT_CASES)
    raw["arrivals"] = {"rate": rate, "rationale": f"{STUDIO_DEFAULT} {reason}"}
    if "warm_up" not in raw:
        raw["warm_up"] = {"length": round(WARM_UP_CASES / rate), "rationale": f"{STUDIO_DEFAULT} {_RATIONALES['warm_up'].format(cases=WARM_UP_CASES)}"}


def apply_suggestion(xml: str, change_ids: list[str], preset: Mapping[str, str]) -> dict:
    """The as-is preset with exactly these catalog changes applied: {xml, params, changes}.

    xml is the current model. It must be the preset's model with some set of
    structural changes (any catalog scenario's model), or ValueError: after a
    hand edit suggestions no longer apply. The result doesn't build on the
    current parameters: it is the catalog's scenario, the model file of its
    structural changes and the as-is parameters with the overrides of its
    changes, minus entries for elements that model lacks, the same as
    Catalog.resolve. So applying a set again, or a smaller one, is the undo.
    changes lists the applied IDs in catalog order.
    """
    catalog, raw = _preset_catalog(preset)
    if parse_bpmn(xml) not in _scenario_models(catalog):
        raise ValueError("the model was edited by hand, so the suggestions no longer apply to it; go back to the preset to use them")
    unknown = sorted(set(change_ids) - set(catalog.ids))
    if unknown:
        raise ValueError(f"no changes {', '.join(unknown)} in the catalog, which has {', '.join(catalog.ids)}")
    combo = [change_id for change_id in catalog.ids if change_id in change_ids]
    model, _ = catalog.resolve(combo)

    files = {frozenset(part.strip() for part in key.split("+")): file for key, file in raw["catalog"].get("models", {}).items()}
    structural = set().union(*files)
    xml_out = preset[files[frozenset(combo) & structural]] if frozenset(combo) & structural else preset[PRESET_MODEL]
    params = copy.deepcopy(raw["params"])
    for change in catalog.changes:
        if change.id in combo:
            for section, entries in change.overrides.items():
                params.setdefault(section, {}).update(copy.deepcopy(entries))
    return {"xml": xml_out, "params": _restrict(params, model), "changes": combo}


def suggestions(xml: str, preset: Mapping[str, str]) -> dict:
    """The change catalog for the suggestions panel, and whether it applies to the current model.

    changes: the catalog's changes in order, each {id, title, driver, heuristic
    {name, ref}, expected_effect, trade_off {time, cost, quality, flexibility,
    note}}, as in the results file. available: whether xml is the preset's model
    with some set of structural changes, so apply_suggestion accepts it.
    """
    catalog, _ = _preset_catalog(preset)
    return {"changes": catalog.entries(), "available": parse_bpmn(xml) in _scenario_models(catalog)}


def _preset_catalog(preset: Mapping[str, str]) -> tuple[Catalog, dict]:
    """The preset's catalog, resolved, and the raw as-is parameters and catalog tables it was read from."""
    model = parse_bpmn(preset[PRESET_MODEL])
    raw_params = tomllib.loads(preset[PRESET_PARAMS])
    raw_catalog = tomllib.loads(preset[PRESET_CATALOG])
    files = {file: parse_bpmn(preset[file]) for file in raw_catalog.get("models", {}).values()}
    catalog = parse_catalog(raw_catalog, files, model=model, params=parse_parameters(raw_params, model), where=PRESET_CATALOG)
    return catalog, {"params": raw_params, "catalog": raw_catalog}


def _scenario_models(catalog: Catalog) -> list[ProcessModel]:
    return [model for model, _ in catalog.scenarios.values()]


def _element_ids(model: ProcessModel) -> dict[str, set[str]]:
    """The IDs each per-element section of the parameters may name: tasks, XOR splits, lanes."""
    return {
        "tasks": {node.id for node in model.nodes_of_type("task")},
        "gateways": {node.id for node in model.xor_splits()},
        "lanes": set(model.lanes),
    }


def _restrict(params: dict, model: ProcessModel) -> dict:
    """The parameter dict without task, XOR-split and lane entries the model doesn't have."""
    known = _element_ids(model)
    return {
        section: {i: entry for i, entry in value.items() if i in known[section]} if section in known else value
        for section, value in params.items()
    }


_PAIRING = ("seed", "replications", "n_cases")


def compare(baseline: dict, variant: dict) -> dict:
    """Compare two simulate_summary runs pair by pair: the variant's saving against the baseline.

    Refuses (ValueError) runs with a different seed, number of replications or
    number of cases, since only then is replication r of both run on the same
    random numbers (common random numbers). Returns:

    - saving: baseline mean cycle time minus the variant's, paired by
      replication, with a 95% CI, like a scenario's saving in the results file
    - saving_share: that saving over the baseline mean (scenarios.saving_share)
    - baseline, variant: {cycle_time} of each run, mean / median / P90
    - lanes: [{lane_id, label, capacity_before, capacity_after, before, after}],
      before / after the utilisation estimate of each run
    - activities: [{activity_id, label, before, after}], the mean wait per run

    A lane or task only one run has gets None on the other side. Rows follow the
    baseline's order (activities longest wait first), then the variant's own.
    """
    differ = [f"{key} {baseline[key]} vs {variant[key]}" for key in _PAIRING if baseline[key] != variant[key]]
    if differ:
        raise ValueError(f"the runs can't be compared pair by pair, they differ in {', '.join(differ)}")
    base_means = np.array(baseline["replication_means"])
    saving = estimate(base_means - np.array(variant["replication_means"]))
    return {
        "saving": saving,
        "saving_share": saving_share(saving, float(base_means.mean())),
        "baseline": {"cycle_time": baseline["cycle_time"]},
        "variant": {"cycle_time": variant["cycle_time"]},
        "lanes": [
            {"lane_id": i, "label": label, "capacity_before": _get(b, "capacity"), "capacity_after": _get(a, "capacity"),
             "before": _get(b, "utilisation"), "after": _get(a, "utilisation")}
            for i, label, b, a in _side_by_side(baseline["lanes"], variant["lanes"], "lane_id")
        ],
        "activities": [
            {"activity_id": i, "label": label, "before": _get(b, "mean"), "after": _get(a, "mean")}
            for i, label, b, a in _side_by_side(baseline["waiting_by_activity"], variant["waiting_by_activity"], "activity_id")
        ],
    }


def _side_by_side(before: list[dict], after: list[dict], key: str) -> list[tuple[str, str, dict | None, dict | None]]:
    """Rows of both runs matched by ID: (id, label, baseline row or None, variant row or None)."""
    b, a = {row[key]: row for row in before}, {row[key]: row for row in after}
    ids = list(dict.fromkeys([*b, *a]))
    return [(i, (b.get(i) or a[i])["label"], b.get(i), a.get(i)) for i in ids]


def _get(row: dict | None, field: str):
    return None if row is None else row[field]


def _per_element(runs: list[dict[str, float]]) -> dict[str, dict[str, float]]:
    """Per element ID, in first-seen order: the estimate over the replications that have it (at least 2)."""
    ids = list(dict.fromkeys(i for run in runs for i in run))
    values = {i: [run[i] for run in runs if i in run] for i in ids}
    return {i: estimate(np.array(v)) for i, v in values.items() if len(v) >= 2}


# The rationale of an entry the user set in the studio's parameter panel. It
# doesn't start with STUDIO_DEFAULT, so the entry stops being shown as a default.
STUDIO_EDIT = "Set in the studio."
_SETTABLE = ("arrivals", "warm_up")  # single entries the panel sets; per element: tasks, gateways, lanes


def set_parameter(xml: str, params: dict, entry: str, fields: dict) -> dict:
    """The parameters with one entry set from the parameter panel: {params, defaults, dropped}.

    entry is "tasks.<id>", "gateways.<id>" (an XOR split), "lanes.<id>",
    "arrivals" or "warm_up"; fields its value as in the parameter file, e.g.
    {"duration": {"triangular": [1, 2, 4]}} or {"capacity": 2}. The entry is
    replaced by fields with the rationale STUDIO_EDIT, so it is no longer a
    default; every other entry stays as it is. The result is completed by
    default_parameters and checked against the model: ValueError, naming the
    entry, when the value is invalid (min above max, probabilities that don't
    sum to 1, capacity 0, ...) or the model has no such element.
    """
    model = parse_bpmn(xml)
    raw = copy.deepcopy(params)
    section, _, element_id = entry.partition(".")
    known = _element_ids(model)
    if section in _SETTABLE and not element_id:
        raw[section] = {**fields, "rationale": STUDIO_EDIT}
    elif section in known and element_id:
        if element_id not in known[section]:
            raise ValueError(f"{entry}: the model has no such element")
        raw.setdefault(section, {})[element_id] = {**fields, "rationale": STUDIO_EDIT}
    else:
        raise ValueError(f"{entry}: the studio sets only {', '.join(_SETTABLE)} and tasks, gateways or lanes by ID")
    filled = default_parameters(xml, raw)
    parse_parameters(filled["params"], model)
    return filled


RESET_CASES = 10_000
RESET_SEED = 0


def fixed_branches(params: dict, gateway_id: str) -> dict:
    """The XOR split's branches with each logistic branch replaced by a fixed share ("reset to fixed").

    The share is the branch's mean probability over the case attributes
    (RESET_CASES cases drawn from the attribute distributions, seed RESET_SEED),
    rounded to 3 decimals, so the split keeps about the same overall rate but
    no longer depends on the attributes. Fixed and "rest" branches stay as they
    are. Pass the result to set_parameter as {"branches": ...}.
    """
    parsed = parse_parameters(params)
    rng = np.random.default_rng(RESET_SEED)
    cases = [{name: d.sample(rng) for name, d in parsed.attributes.items()} for _ in range(RESET_CASES)]
    branches = dict(params["gateways"][gateway_id]["branches"])
    for flow_id, p in parsed.branch_probabilities[gateway_id].flows.items():
        if isinstance(p, Logistic):
            branches[flow_id] = round(float(np.mean([p.probability(case) for case in cases])), 3)
    return branches


EXPORT_HEADER = "# Parameter file exported from the simulation studio. Read it with bpmopt.parameters.load_parameters.\n"


def params_to_toml(params: dict) -> str:
    """The parameter dict as a parameter file: TOML that load_parameters reads back to the same tables.

    Laid out like the hand-written files: top-level keys first, then one
    [section] per single entry and one [section.id] per entry of a collection,
    each value on one line (tables inline). Pyodide has tomllib but no TOML
    writer, hence this one; it only needs the types a parameter file holds.
    """
    lines = [EXPORT_HEADER.rstrip("\n")]
    lines += [f"{_toml_key(key)} = {_toml_value(value)}" for key, value in params.items() if not isinstance(value, dict)]
    for section, value in params.items():
        if not isinstance(value, dict):
            continue
        if value and all(isinstance(entry, dict) for entry in value.values()):
            tables = [(f"{_toml_key(section)}.{_toml_key(key)}", entry) for key, entry in value.items()]
        else:
            tables = [(_toml_key(section), value)]
        for header, table in tables:
            lines += ["", f"[{header}]", *(f"{_toml_key(key)} = {_toml_value(v)}" for key, v in table.items())]
    return "\n".join(lines) + "\n"


def _toml_key(key: str) -> str:
    return key if key and all(c.isascii() and (c.isalnum() or c in "_-") for c in key) else json.dumps(key, ensure_ascii=False)


def _toml_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)  # shortest text that reads back to the same float; inf and nan are TOML too
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)  # a JSON string is a valid TOML basic string
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(v) for v in value) + "]"
    if isinstance(value, dict):
        return "{ " + ", ".join(f"{_toml_key(k)} = {_toml_value(v)}" for k, v in value.items()) + " }" if value else "{}"
    raise TypeError(f"can't write {value!r} to a parameter file")


def lint_xml(xml: str) -> list[dict]:
    """The book's lint rules on a BPMN string: the same violations, in the same order, as lint on its file.

    Each is {rule, severity ("error" or "warning"), element_id, message}. A
    document that isn't one readable BPMN process raises a ValueError that starts
    "Not a readable BPMN document", which the page shows in place of the violations.
    """
    try:
        model = parse_bpmn(xml)
    except ElementTree.ParseError as e:
        raise ValueError(f"Not a readable BPMN document: the XML has a {e}.") from e
    except KeyError as e:
        raise ValueError(f"Not a readable BPMN document: an element has no {e.args[0]} attribute.") from e
    except ValueError as e:
        raise ValueError(f"Not a readable BPMN document: {str(e).removeprefix('BPMN: ')}.") from e
    return [
        {"rule": v.rule, "severity": v.severity, "element_id": v.element_id, "message": v.message}
        for v in lint_model(model)
    ]
