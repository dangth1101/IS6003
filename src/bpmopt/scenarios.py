"""Change catalog and scenario runner (Phase 6: evaluate the redesign).

A scenario is a set of change IDs. It resolves to a process model and a parameter
set: the as-is ones, with the catalog's model for its structural changes and the
overrides of every change applied. The runner simulates every combination of
changes (2^k scenarios) with common random numbers and reports cycle time and
the saving against the as-is scenario with 95% confidence intervals.

The catalog file (TOML) looks like:

    version = "draft-1"

    [changes.C1]                              # one table per change; the ID is the key
    title = "Run security testing next to functional testing"
    driver = "Testing has the longest wait."  # the delay driver it targets (ML or baseline)
    heuristic = { name = "Parallelism", ref = "Appendix A.3" }
    expected_effect = "..."
    trade_off = { time = "better", cost = "worse", quality = "neutral", flexibility = "neutral", note = "..." }

    [changes.C1.overrides.tasks.Task_X]       # optional: parameter file entries this change adds or
    duration = { triangular = [1, 2, 4] }     # replaces. Only lanes, tasks and gateways, each with
    rationale = "..."                         # its own rationale.

    [models]                                  # structural changes: the BPMN file (relative to this
    C1 = "to_be_c1.bpmn"                      # file) for each combination of them, so every
    C2 = "to_be_c2.bpmn"                      # combination needs one
    "C1+C2" = "to_be_c1_c2.bpmn"

A change listed in [models] is structural; the others only change parameters.
Entries for tasks, gateways and lanes that aren't in a scenario's model are
dropped, so a change that removes a task needs no override for it.
"""

import math
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, replace
from itertools import combinations
from pathlib import Path

import jsonschema
import numpy as np
from scipy.stats import t as student_t

from bpmopt.analysis import cycle_times
from bpmopt.bpmn import ProcessModel, read_bpmn
from bpmopt.contract import validate_changes
from bpmopt.parameters import Parameters, apply_overrides, assumptions, check_parameters
from bpmopt.simulation import simulate


@dataclass(frozen=True)
class Change:
    id: str
    title: str
    driver: str
    heuristic: dict[str, str]  # name, ref
    expected_effect: str
    trade_off: dict[str, str]  # time, cost, quality, flexibility (better / worse / neutral) and a note
    overrides: dict  # parameter file layout, sections lanes, tasks and gateways

    def entry(self) -> dict:
        """The change as a row of the results file's change catalog."""
        return {
            "id": self.id,
            "title": self.title,
            "driver": self.driver,
            "heuristic": dict(self.heuristic),
            "expected_effect": self.expected_effect,
            "trade_off": dict(self.trade_off),
        }


@dataclass(frozen=True)
class Catalog:
    version: str
    changes: tuple[Change, ...]
    scenarios: dict[frozenset[str], tuple[ProcessModel, Parameters]]  # every combination of change IDs, resolved

    @property
    def ids(self) -> list[str]:
        return [change.id for change in self.changes]

    def resolve(self, change_ids: list[str] | set[str] | tuple[str, ...]) -> tuple[ProcessModel, Parameters]:
        """The process model and parameters a scenario simulates."""
        key = frozenset(change_ids)
        if key not in self.scenarios:
            raise KeyError(f"no changes {sorted(key - set(self.ids))} in the catalog")
        return self.scenarios[key]

    def entries(self) -> list[dict]:
        """The `changes` section of the results file."""
        return [change.entry() for change in self.changes]

    def assumptions(self) -> list[dict]:
        """Assumptions table rows for every parameter a change adds or replaces, each marked with its change.

        Values are described from the parsed overrides, like the as-is rows.
        Rows follow the catalog order, then the order of the change's overrides.
        """
        _, as_is = self.resolve([])
        rows = []
        for change in self.changes:
            entries = [f"{section}.{element_id}" for section, items in change.overrides.items() for element_id in items]
            by_entry = {row["parameter"].rsplit(".", 1)[0]: row for row in assumptions(apply_overrides(as_is, change.overrides))}
            rows += [{**by_entry[entry], "change": change.id} for entry in entries]
        return rows


_CHANGE_FIELDS = ("title", "driver", "heuristic", "expected_effect", "trade_off")


def load_catalog(path: str | Path, *, model: ProcessModel, params: Parameters) -> Catalog:
    """Read a change catalog and resolve every combination of its changes.

    model and params are the as-is ones. Every scenario is resolved and checked
    against its model here, so a broken combination fails before any simulation.
    """
    path = Path(path)
    with open(path, "rb") as f:
        raw = tomllib.load(f)
    return parse_catalog(raw, _ModelFiles(path.parent), model=model, params=params, where=path.name)


class _ModelFiles(Mapping):
    """The models of a catalog's [models] files, read from its folder only when a combination is accepted."""

    def __init__(self, folder: Path):
        self._folder = folder

    def __getitem__(self, file: str) -> ProcessModel:
        return read_bpmn(self._folder / file)

    def __iter__(self):
        return (path.name for path in self._folder.glob("*.bpmn"))

    def __len__(self) -> int:
        return sum(1 for _ in self)


def parse_catalog(
    raw: dict,
    model_files: Mapping[str, ProcessModel],
    *,
    model: ProcessModel,
    params: Parameters,
    where: str = "catalog",
) -> Catalog:
    """Same as load_catalog, for a catalog already read into a dict, e.g. by the studio in the browser.

    model_files holds the model of each file name in [models]; where names the
    catalog in error messages.
    """
    unknown = set(raw) - {"version", "changes", "models"}
    if unknown:
        raise ValueError(f"{where}: unknown sections {sorted(unknown)}, expected version, changes and models")
    if not isinstance(raw.get("version"), str):
        raise ValueError(f'{where}: version is missing: add a line like version = "draft-1" at the top')
    changes = tuple(_change(where, change_id, entry) for change_id, entry in raw.get("changes", {}).items())
    if not changes:
        raise ValueError(f"{where}: the catalog has no changes")
    ids = [change.id for change in changes]
    models = _models(where, raw.get("models", {}), ids, model_files)
    _check_overrides(where, changes, [model, *models.values()])
    check_parameters(params, model)  # before _restrict, which would hide a typo in the as-is parameters

    structural = set().union(*models)
    scenarios = {}
    for combo in _combinations(ids):
        scenario_model = models.get(frozenset(combo) & structural, model)
        scenario_params = params
        for change in changes:
            if change.id in combo:
                try:
                    scenario_params = apply_overrides(scenario_params, change.overrides)
                except ValueError as e:
                    raise ValueError(f"{where}: changes.{change.id}.overrides: {e}") from e
        scenario_params = _restrict(scenario_params, scenario_model)
        try:
            check_parameters(scenario_params, scenario_model)
        except ValueError as e:
            raise ValueError(f"{where}: scenario [{', '.join(combo)}]: {e}") from e
        scenarios[frozenset(combo)] = (scenario_model, scenario_params)
    return Catalog(raw["version"], changes, scenarios)


def _change(where: str, change_id: str, entry: dict) -> Change:
    fields = {key: value for key, value in entry.items() if key != "overrides"}
    missing = [name for name in _CHANGE_FIELDS if name not in fields]
    unknown = sorted(set(fields) - set(_CHANGE_FIELDS))
    if missing or unknown:
        problems = ([f"missing {', '.join(missing)}"] if missing else []) + ([f"unknown {', '.join(unknown)}"] if unknown else [])
        raise ValueError(f"{where}: changes.{change_id}: {'; '.join(problems)}. A change needs {', '.join(_CHANGE_FIELDS)}")
    change = Change(id=change_id, overrides=entry.get("overrides", {}), **fields)
    try:
        validate_changes([change.entry()])
    except jsonschema.ValidationError as e:
        field_path = ".".join(str(p) for p in list(e.absolute_path)[1:])
        raise ValueError(f"{where}: changes.{change_id}.{field_path}: {e.message}") from e
    return change


def _models(where: str, raw: dict[str, str], ids: list[str], files: Mapping[str, ProcessModel]) -> dict[frozenset[str], ProcessModel]:
    """The model of each combination of structural changes, from its file. Every combination needs one."""
    models: dict[frozenset[str], ProcessModel] = {}
    for key, file in raw.items():
        combo = frozenset(part.strip() for part in key.split("+"))
        unknown = sorted(combo - set(ids))
        if unknown:
            raise ValueError(f"{where}: models.{key}: {', '.join(unknown)} aren't changes in the catalog")
        if combo in models:
            raise ValueError(f"{where}: models.{key}: that combination already has a model")
        try:
            models[combo] = files[file]
        except KeyError:
            raise ValueError(f"{where}: models.{key}: no model file {file!r} given") from None
    structural = [change_id for change_id in ids if any(change_id in combo for combo in models)]
    missing = ["+".join(combo) for combo in _combinations(structural) if combo and frozenset(combo) not in models]
    if missing:
        raise ValueError(f"{where}: [models] needs a model for every combination of structural changes, missing: {', '.join(missing)}")
    return models


def _check_overrides(where: str, changes: tuple[Change, ...], models: list[ProcessModel]) -> None:
    """Each override names an element of some model (a gateway must be an XOR-split), and no two changes override the same entry."""
    what = {"tasks": "task", "gateways": "XOR-split", "lanes": "lane"}
    known = {
        "tasks": {node.id for m in models for node in m.nodes_of_type("task")},
        "gateways": {node.id for m in models for node in m.xor_splits()},
        "lanes": {lane_id for m in models for lane_id in m.lanes},
    }
    owner: dict[str, str] = {}
    for change in changes:
        for section, entries in change.overrides.items():
            for element_id in entries if section in known else ():
                entry = f"{section}.{element_id}"
                if element_id not in known[section]:
                    raise ValueError(f"{where}: changes.{change.id}.overrides.{entry}: no model in the catalog has a {what[section]} with this ID")
                if entry in owner:
                    raise ValueError(f"{where}: {owner[entry]} and {change.id} both override {entry}, so their combination is ambiguous")
                owner[entry] = change.id


def _combinations(ids: list[str]) -> list[tuple[str, ...]]:
    """Every subset of ids, smallest first, each in catalog order."""
    return [combo for k in range(len(ids) + 1) for combo in combinations(ids, k)]


def _restrict(params: Parameters, model: ProcessModel) -> Parameters:
    """Drop the task, gateway and lane entries the model doesn't have."""
    tasks = {node.id for node in model.nodes_of_type("task")}
    gateways = {node.id for node in model.xor_splits()}
    keep = {f"tasks.{i}" for i in tasks} | {f"gateways.{i}" for i in gateways} | {f"lanes.{i}" for i in model.lanes}
    return replace(
        params,
        task_durations={k: v for k, v in params.task_durations.items() if k in tasks},
        branch_probabilities={k: v for k, v in params.branch_probabilities.items() if k in gateways},
        lane_capacities={k: v for k, v in params.lane_capacities.items() if k in model.lanes},
        rationales={k: v for k, v in params.rationales.items() if k.split(".")[0] not in ("tasks", "gateways", "lanes") or k in keep},
    )


def replication_seeds(seed: int, replications: int) -> list[int]:
    """The seed of each replication. Every scenario uses the same ones (common random numbers)."""
    return [int(np.random.SeedSequence([seed, r]).generate_state(1)[0]) for r in range(replications)]


def run_scenarios(catalog: Catalog, *, n_cases: int, seed: int, replications: int = 30) -> list[dict]:
    """Simulate every scenario R times and return the `scenarios` section of the results file.

    Replication r of every scenario runs with the same seed, so the scenarios see
    the same arrivals, case attributes and draws per task and gateway (common
    random numbers). Each replication gives one mean, median and P90 cycle time
    per scenario; the estimate is their average over replications, with a 95%
    t-interval. The saving is the as-is mean cycle time minus the scenario's,
    paired by replication, so the CI only reflects how the difference varies.
    saving_share is that saving over the as-is mean (see saving_share), and
    replication_means keeps each replication's mean cycle time, so
    any two scenarios can be compared pair by pair later (see ablation).
    Cycle times stop at the as-is parameters' cut-off (cycle_time_end), which no
    change can override, so every scenario is measured over the same span.
    """
    if replications < 2:
        raise ValueError(f"need at least 2 replications for a confidence interval, got {replications}")
    seeds = replication_seeds(seed, replications)
    stats = {}
    for combo in _combinations(catalog.ids):
        model, params = catalog.resolve(combo)
        runs = [cycle_times(simulate(model, params, n_cases=n_cases, seed=s), params.cycle_time_end) for s in seeds]
        stats[combo] = {
            "mean": np.array([ct.mean() for ct in runs]),
            "median": np.array([ct.median() for ct in runs]),
            "p90": np.array([ct.quantile(0.9) for ct in runs]),
        }
    as_is = stats[()]["mean"]
    scenarios = []
    for combo, s in stats.items():
        saving = estimate(as_is - s["mean"])
        scenarios.append(
            {
                "changes": list(combo),
                "cycle_time": {name: estimate(values) for name, values in s.items()},
                "saving": saving,
                "saving_share": saving_share(saving, float(as_is.mean())),
                "replication_means": [float(m) for m in s["mean"]],
            }
        )
    return scenarios


def saving_share(saving: dict[str, float], as_is_mean: float) -> dict[str, float]:
    """The saving as a share of the as-is mean cycle time: the saving and its CI bounds, each divided by that mean.

    The as-is mean is treated as fixed, so the share always equals the days the
    page shows next to it (saving / as-is mean). Its own uncertainty is in the
    as-is cycle time CI, not in the share's.
    """
    return {k: v / as_is_mean for k, v in saving.items()}


def ablation(scenarios: list[dict]) -> list[dict]:
    """Per change: its saving alone (with CI), and what it adds to the full design.

    Both views are read off the full factorial (the `ablation` section of the
    results file): `alone` is the saving of the scenario with only that change,
    `full_minus` is how many days longer the mean cycle time gets when the change
    is dropped from the full design. Its CI pairs the two scenarios by
    replication, like the saving does. A negative full_minus means the full
    design is faster without that change.
    """
    full = full_design(scenarios)
    full_means = np.array(full["replication_means"])
    return [
        {
            "change": change_id,
            "alone": find_scenario(scenarios, [change_id])["saving"],
            "full_minus": estimate(np.array(find_scenario(scenarios, set(full["changes"]) - {change_id})["replication_means"]) - full_means),
        }
        for change_id in full["changes"]
    ]


def headline(scenarios: list[dict], ablation_rows: list[dict]) -> dict:
    """The `headline` section: the proposed design, the change it needs most, and the best combination.

    The proposed design is the full design, every change in the catalog. The
    change it needs most is the one with the largest full_minus: dropping it
    costs the full design the most days. The best combination is the scenario
    with the largest mean saving, which can be smaller than the full design when
    changes get in each other's way.
    """
    best = max(scenarios, key=lambda s: s["saving"]["value"])
    top = max(ablation_rows, key=lambda row: row["full_minus"]["value"])
    return {"changes": list(full_design(scenarios)["changes"]), "top_change": top["change"], "best": list(best["changes"])}


def find_scenario(scenarios: list[dict], changes) -> dict | None:
    """The scenario that applies exactly these change IDs, in any order. None if there is none."""
    key = frozenset(changes)
    return next((s for s in scenarios if frozenset(s["changes"]) == key), None)


def full_design(scenarios: list[dict]) -> dict:
    """The scenario with every change of the catalog: the proposed design."""
    return max(scenarios, key=lambda s: len(s["changes"]))


def estimate(values: np.ndarray) -> dict[str, float]:
    """Mean of the values with a 95% t-interval."""
    mean = float(values.mean())
    half_width = float(student_t.ppf(0.975, len(values) - 1)) * float(values.std(ddof=1)) / math.sqrt(len(values))
    return {"value": mean, "ci_low": mean - half_width, "ci_high": mean + half_width}
