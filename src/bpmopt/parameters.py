"""Load the human-editable parameter file (TOML) that drives the simulator.

Time unit: working days on a continuous clock. Every entry needs a rationale,
which goes into the assumptions table of the results. The file looks like:

    version = "draft-1"

    [arrivals]                      # optional; without it every case arrives at time 0
    rate = 0.25                     # cases per working day (Poisson)
    rationale = "..."

    [warm_up]                       # optional; needs [arrivals]
    length = 100                    # working days
    rationale = "..."

    [attributes.complexity]         # drawn once per case, in the log as a column
    distribution = { choice = [1, 2, 3], weights = [0.3, 0.5, 0.2] }   # or labels: ["web", "mobile"]
    rationale = "..."               # also { poisson = 1.5 } and { triangular = [min, mode, max] }

    [lanes.Lane_Dev]                # optional; a lane not listed is unlimited
    capacity = 3
    rationale = "..."

    [tasks.Task_Build]              # every task in the model
    duration = { triangular = [10, 20, 45] }   # or { fixed = 20 }
    rationale = "..."

    [tasks.Task_Test]               # a duration can scale with the case attributes
    duration = { triangular = [2, 4, 8], scale = { integrations = 0.1, project_type = { mobile = 0.5 } } }
    rationale = "..."

    [gateways.Gateway_TestsPassed]  # every XOR-split, one branch per outgoing flow
    branches = { Flow_Ok = "rest", Flow_Rework = { logistic = { intercept = -2, complexity = 0.8, project_type = { mobile = 1.5 } } } }
    rationale = "..."

A branch is a fixed probability, "rest" (whatever the others leave), or a
logistic of the case attributes. A numeric attribute takes a number; a label
attribute takes a table of label -> coefficient, unlisted labels count 0.

A scaled duration multiplies the drawn duration by 1 + the sum of its terms,
written the same way as logistic terms. The example above takes 10% longer per
integration and 50% longer for a mobile project.
"""

import math
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np

from bpmopt.bpmn import ProcessModel


@dataclass(frozen=True)
class FixedDuration:
    value: float

    @property
    def mean(self) -> float:
        return self.value

    def sample(self, rng: np.random.Generator, attributes: Mapping[str, "AttributeValue"] | None = None) -> float:
        return self.value


AttributeValue = str | int | float


@dataclass(frozen=True)
class Choice:
    """Pick one of `values` with the given weights. Values are labels (str) or numbers."""

    values: tuple[AttributeValue, ...]
    weights: tuple[float, ...]

    def sample(self, rng: np.random.Generator) -> AttributeValue:
        return self.values[rng.choice(len(self.values), p=self.weights)]


@dataclass(frozen=True)
class Poisson:
    mean: float

    def sample(self, rng: np.random.Generator) -> int:
        return int(rng.poisson(self.mean))


@dataclass(frozen=True)
class Triangular:
    low: float
    mode: float
    high: float

    @property
    def mean(self) -> float:
        return (self.low + self.mode + self.high) / 3

    def sample(self, rng: np.random.Generator, attributes: Mapping[str, AttributeValue] | None = None) -> float:
        return float(rng.triangular(self.low, self.mode, self.high))


Distribution = Choice | Poisson | Triangular
Coefficients = dict[str, float | dict[str, float]]  # attribute -> coefficient, or label -> coefficient


def _linear(coefficients: Coefficients, attributes: Mapping[str, AttributeValue]) -> float:
    """Sum of the attribute terms: coefficient x value, or the coefficient of the label (0 if not listed)."""
    total = 0.0
    for name, coefficient in coefficients.items():
        value = attributes[name]
        total += coefficient.get(value, 0.0) if isinstance(coefficient, dict) else coefficient * value
    return total


@dataclass(frozen=True)
class ScaledDuration:
    """A base duration times 1 + the attribute terms, e.g. builds that take longer per integration.

    `mean_factor` is the mean of that factor over the attribute distributions in
    the parameter file. The factor is linear and drawn independently of the base,
    so mean = base mean x mean factor exactly.
    """

    base: FixedDuration | Triangular
    coefficients: Coefficients
    mean_factor: float

    @property
    def mean(self) -> float:
        return self.base.mean * self.mean_factor

    def mean_given(self, attributes: Mapping[str, AttributeValue]) -> float:
        """Mean duration for a case with these attributes."""
        return self.base.mean * (1 + _linear(self.coefficients, attributes))

    def sample(self, rng: np.random.Generator, attributes: Mapping[str, AttributeValue] | None = None) -> float:
        if attributes is None:
            raise ValueError("a scaled duration needs the case attributes")
        factor = 1 + _linear(self.coefficients, attributes)
        if factor <= 0:
            raise ValueError(f"duration scale factor {factor:g} isn't positive for attributes {dict(attributes)}")
        return self.base.sample(rng) * factor


Duration = FixedDuration | Triangular | ScaledDuration


@dataclass(frozen=True)
class Logistic:
    """P(branch) = 1 / (1 + exp(-z)), z = intercept + sum of attribute effects.

    A numeric attribute adds coefficient x value. A label attribute adds the
    coefficient of its label, or 0 for a label not listed.
    """

    intercept: float
    coefficients: Coefficients

    def probability(self, attributes: Mapping[str, AttributeValue]) -> float:
        z = self.intercept + _linear(self.coefficients, attributes)
        return 1 / (1 + math.exp(-z))


REST = "rest"  # the branch that gets whatever probability the other branches leave


@dataclass(frozen=True)
class Branches:
    """Branching probabilities of one XOR-split (book p.257), keyed by outgoing flow ID.

    Each flow has a fixed probability, a Logistic of the case attributes, or REST.
    """

    flows: dict[str, float | Logistic | str]

    @property
    def depends_on_attributes(self) -> bool:
        return any(isinstance(p, Logistic) for p in self.flows.values())

    def probabilities(self, attributes: Mapping[str, AttributeValue]) -> dict[str, float]:
        probabilities = {
            flow_id: p.probability(attributes) if isinstance(p, Logistic) else p
            for flow_id, p in self.flows.items()
            if p != REST
        }
        for flow_id, p in self.flows.items():
            if p == REST:
                probabilities[flow_id] = 1 - sum(probabilities.values())
        return probabilities


@dataclass(frozen=True)
class Parameters:
    version: str
    task_durations: dict[str, Duration]  # task ID -> duration
    arrival_rate: float | None = None  # cases per working day (Poisson); None: every case arrives at time 0
    lane_capacities: dict[str, int] = field(default_factory=dict)  # lane ID -> resources; a lane not listed is unlimited
    warm_up: float = 0.0  # working days; cases arriving before this are simulated but left out of the log
    branch_probabilities: dict[str, Branches] = field(default_factory=dict)  # XOR-split ID -> its branches
    attributes: dict[str, Distribution] = field(default_factory=dict)  # attribute name -> distribution, drawn once per case
    rationales: dict[str, str] = field(default_factory=dict)  # entry, e.g. "tasks.Task_X" or "arrivals" -> why this value


# What each entry holds besides its rationale. Single entries are one table; collections hold one table per ID.
_SINGLE_ENTRIES = {"arrivals": "rate", "warm_up": "length"}
_COLLECTIONS = {"attributes": "distribution", "lanes": "capacity", "tasks": "duration", "gateways": "branches"}


def load_parameters(path: str | Path, model: ProcessModel | None = None) -> Parameters:
    """Read and validate a parameter file. With a model, also check every ID against it (see check_parameters)."""
    with open(path, "rb") as f:
        raw = tomllib.load(f)
    rationales = _check_layout(raw)
    arrival_rate = float(raw["arrivals"]["rate"]) if "arrivals" in raw else None
    if arrival_rate is not None and arrival_rate <= 0:
        raise ValueError(f"arrivals.rate must be positive, got {arrival_rate}")
    warm_up = float(raw["warm_up"]["length"]) if "warm_up" in raw else 0.0
    if warm_up < 0:
        raise ValueError(f"warm_up.length must not be negative, got {warm_up}")
    if warm_up > 0 and arrival_rate is None:
        raise ValueError("warm_up needs an arrival rate: without [arrivals] every case arrives at time 0")
    capacities = {lane_id: _capacity(lane_id, entry["capacity"]) for lane_id, entry in raw.get("lanes", {}).items()}
    attributes = {name: _distribution(name, entry["distribution"]) for name, entry in raw.get("attributes", {}).items()}
    durations = {task_id: _duration(task_id, entry["duration"], attributes) for task_id, entry in raw.get("tasks", {}).items()}
    branches = {
        gateway_id: _branches(gateway_id, entry["branches"], attributes) for gateway_id, entry in raw.get("gateways", {}).items()
    }
    params = Parameters(
        version=str(raw["version"]),
        task_durations=durations,
        arrival_rate=arrival_rate,
        lane_capacities=capacities,
        warm_up=warm_up,
        branch_probabilities=branches,
        attributes=attributes,
        rationales=rationales,
    )
    if model is not None:
        check_parameters(params, model)
    return params


# What a redesign may change. Arrivals, attributes and the warm-up describe the demand and the
# run, not the design, so they stay the same in every scenario.
_OVERRIDABLE = ("lanes", "tasks", "gateways")


def apply_overrides(params: Parameters, overrides: dict) -> Parameters:
    """Return params with the entries in overrides added or replaced.

    overrides uses the parameter file layout, e.g. {"tasks": {"Task_X": {"duration":
    {"fixed": 3}, "rationale": "..."}}}. Only lanes, tasks and gateways can be
    overridden. Every entry needs its own rationale, which replaces the old one in
    the assumptions table. IDs aren't checked against a model here.
    """
    unknown = set(overrides) - set(_OVERRIDABLE)
    if unknown:
        raise ValueError(f"can't override {', '.join(sorted(unknown))}: only {', '.join(_OVERRIDABLE)} can change between scenarios")
    rationales = _check_layout({"version": params.version, **overrides})
    durations = {task_id: _duration(task_id, entry["duration"], params.attributes) for task_id, entry in overrides.get("tasks", {}).items()}
    capacities = {lane_id: _capacity(lane_id, entry["capacity"]) for lane_id, entry in overrides.get("lanes", {}).items()}
    branches = {
        gateway_id: _branches(gateway_id, entry["branches"], params.attributes) for gateway_id, entry in overrides.get("gateways", {}).items()
    }
    return replace(
        params,
        task_durations=params.task_durations | durations,
        lane_capacities=params.lane_capacities | capacities,
        branch_probabilities=params.branch_probabilities | branches,
        rationales=params.rationales | rationales,
    )


def assumptions(params: Parameters) -> list[dict]:
    """The assumptions table: one row per parameter entry, with its value and rationale.

    Built from the parsed values rather than the file text, so parameters changed
    in code (e.g. a scenario's overrides) show up as they are simulated.
    """
    values: dict[str, tuple[str, AttributeValue]] = {}
    if params.arrival_rate is not None:
        values["arrivals"] = ("rate", params.arrival_rate)
    if params.warm_up:
        values["warm_up"] = ("length", params.warm_up)
    values |= {f"attributes.{name}": ("distribution", _describe(d)) for name, d in params.attributes.items()}
    values |= {f"lanes.{lane_id}": ("capacity", capacity) for lane_id, capacity in params.lane_capacities.items()}
    values |= {f"tasks.{task_id}": ("duration", _describe(d)) for task_id, d in params.task_durations.items()}
    values |= {f"gateways.{gateway_id}": ("branches", _describe(b)) for gateway_id, b in params.branch_probabilities.items()}
    missing = [entry for entry in values if not params.rationales.get(entry)]
    if missing:
        raise ValueError(f"no rationale for {', '.join(missing)}")
    return [{"parameter": f"{entry}.{key}", "value": value, "rationale": params.rationales[entry]} for entry, (key, value) in values.items()]


def _describe(value: object) -> AttributeValue:
    match value:
        case FixedDuration(v):
            return v
        case Triangular(low, mode, high):
            return f"triangular({_n(low)}, {_n(mode)}, {_n(high)})"
        case Poisson(mean):
            return f"poisson({_n(mean)})"
        case Choice(choices, weights):
            return "choice(" + ", ".join(f"{_n(v)}: {_n(w)}" for v, w in zip(choices, weights)) + ")"
        case Branches(flows):
            return ", ".join(f"{flow_id}: {_describe(p) if isinstance(p, Logistic) else _n(p)}" for flow_id, p in flows.items())
        case ScaledDuration(base, coefficients):
            return f"{_n(_describe(base))} × ({_terms(1.0, coefficients)})"
        case Logistic(intercept, coefficients):
            return f"logistic({_terms(intercept, coefficients)})"
    raise TypeError(f"can't describe {value!r}")


def _terms(constant: float, coefficients: Coefficients) -> str:
    terms = [(c, name) for name, c in coefficients.items() if not isinstance(c, dict)]
    terms += [(c, f"[{name} = {label}]") for name, table in coefficients.items() if isinstance(table, dict) for label, c in table.items()]
    return _n(constant) + "".join(f" {'-' if c < 0 else '+'} {_n(abs(c))} × {term}" for c, term in terms)


def _n(value: AttributeValue) -> str:
    return f"{value:g}" if isinstance(value, float) else str(value)


def _check_layout(raw: dict) -> dict[str, str]:
    """Check sections and keys, and that every entry has a rationale. Returns entry -> rationale."""
    if not isinstance(raw.get("version"), str):
        raise ValueError('version is missing: add a line like version = "draft-1" at the top')
    entries: dict[str, tuple[dict, str]] = {}
    for section, value in raw.items():
        if section in _SINGLE_ENTRIES:
            entries[section] = (value, _SINGLE_ENTRIES[section])
        elif section in _COLLECTIONS:
            entries |= {f"{section}.{key}": (entry, _COLLECTIONS[section]) for key, entry in value.items()}
        elif section != "version":
            known = ", ".join([*_SINGLE_ENTRIES, *_COLLECTIONS])
            raise ValueError(f"unknown section {section!r}, expected one of: version, {known}")
    rationales = {}
    for where, (entry, key) in entries.items():
        if not isinstance(entry, dict):
            raise ValueError(f"{where}: expected a table with {key} and rationale, got {entry!r}")
        unknown = set(entry) - {key, "rationale"}
        if unknown:
            raise ValueError(f"{where}: unknown keys {sorted(unknown)}, expected {key} and rationale")
        if key not in entry:
            raise ValueError(f"{where}: {key} is missing")
        rationale = entry.get("rationale")
        if not isinstance(rationale, str) or not rationale.strip():
            raise ValueError(f"{where}: rationale is missing. Every parameter needs one for the assumptions table")
        rationales[where] = rationale.strip()
    return rationales


def check_parameters(params: Parameters, model: ProcessModel) -> None:
    """Raise ValueError listing every ID that is missing from the parameters or unknown to the model.

    Every task needs a duration, and every XOR-split needs a branch for each of
    its outgoing flows. Tasks, lanes and gateways that aren't in the model are
    errors too, since they are usually typos.
    """
    tasks = {node.id for node in model.nodes_of_type("task")}
    splits = {node.id: {f.id for f in model.outgoing(node.id)} for node in model.xor_splits()}
    problems = [f"tasks.{task_id}: task has no duration" for task_id in sorted(tasks - set(params.task_durations))]
    problems += [f"gateways.{gateway_id}: XOR-split has no branches" for gateway_id in sorted(set(splits) - set(params.branch_probabilities))]
    problems += [f"tasks.{task_id}: no task with this ID in the model" for task_id in params.task_durations if task_id not in tasks]
    problems += [f"lanes.{lane_id}: no lane with this ID in the model" for lane_id in params.lane_capacities if lane_id not in model.lanes]
    for gateway_id, branches in params.branch_probabilities.items():
        if gateway_id not in splits:
            problems.append(f"gateways.{gateway_id}: no XOR-split with this ID in the model")
        elif set(branches.flows) != splits[gateway_id]:
            problems.append(f"gateways.{gateway_id}.branches: expected one branch per outgoing flow, {sorted(splits[gateway_id])}")
    if problems:
        raise ValueError(f"parameters don't match model {model.process_id}:\n  " + "\n  ".join(problems))


def _distribution(name: str, spec: dict) -> Distribution:
    from bpmopt.simulation import LOG_COLUMNS  # here, not at the top: simulation imports this module

    if name in LOG_COLUMNS:
        raise ValueError(f"attributes.{name}: the name is taken by a log column, pick another")
    where = f"attributes.{name}.distribution"
    if set(spec) == {"choice", "weights"}:
        values, weights = tuple(spec["choice"]), tuple(float(w) for w in spec["weights"])
        if not values or len(values) != len(weights):
            raise ValueError(f"{where}: choice and weights need the same, non-zero length")
        all_labels = all(isinstance(v, str) for v in values)
        all_numbers = all(isinstance(v, int | float) and not isinstance(v, bool) for v in values)
        if not (all_labels or all_numbers):
            raise ValueError(f"{where}: choice must be all labels or all numbers, got {list(values)}")
        if any(w < 0 for w in weights) or abs(sum(weights) - 1) > 1e-9:
            raise ValueError(f"{where}: weights must not be negative and must sum to 1, got {list(weights)}")
        return Choice(values, weights)
    if set(spec) == {"poisson"}:
        return Poisson(float(spec["poisson"]))
    if set(spec) == {"triangular"}:
        return Triangular(*_triangular(where, spec["triangular"]))
    raise ValueError(f"{where}: unsupported distribution {spec!r}")


def _triangular(where: str, values: list) -> tuple[float, float, float]:
    if len(values) != 3:
        raise ValueError(f"{where}: triangular needs [min, mode, max], got {values!r}")
    low, mode, high = (float(v) for v in values)
    if not low <= mode <= high or low == high:
        raise ValueError(f"{where}: triangular needs min <= mode <= max and min < max, got {values!r}")
    return low, mode, high


def _branches(gateway_id: str, spec: dict, attributes: dict[str, Distribution]) -> Branches:
    where = f"gateways.{gateway_id}.branches"
    flows = {flow_id: _branch(f"{where}.{flow_id}", p, attributes) for flow_id, p in spec.items()}
    fixed = [p for p in flows.values() if isinstance(p, float)]
    n_rest = sum(p == REST for p in flows.values())
    if any(isinstance(p, Logistic) for p in flows.values()) and (len(flows) != 2 or n_rest != 1):
        raise ValueError(f'{where}: a logistic branch needs exactly one other branch, set to "rest"')
    if n_rest > 1:
        raise ValueError(f'{where}: only one branch can be "rest"')
    total = sum(fixed)
    if any(not 0 <= p <= 1 for p in fixed) or total > 1 + 1e-9 or (n_rest == 0 and abs(total - 1) > 1e-9):
        raise ValueError(f'{where}: probabilities must lie in [0, 1] and sum to 1 (or at most 1 with a "rest" branch), got {spec!r}')
    return Branches(flows)


def _branch(where: str, value: object, attributes: dict[str, Distribution]) -> float | Logistic | str:
    if value == REST:
        return REST
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, dict) and set(value) == {"logistic"}:
        terms = dict(value["logistic"])
        intercept = float(terms.pop("intercept", 0.0))
        return Logistic(intercept, {name: _coefficient(f"{where}.logistic.{name}", c, attributes.get(name)) for name, c in terms.items()})
    raise ValueError(f'{where}: expected a probability, "rest" or {{ logistic = {{ ... }} }}, got {value!r}')


def _coefficient(where: str, value: object, attribute: Distribution | None) -> float | dict[str, float]:
    if attribute is None:
        raise ValueError(f"{where}: no attribute with that name in [attributes]")
    labels = isinstance(attribute, Choice) and any(isinstance(v, str) for v in attribute.values)
    if labels and isinstance(value, dict):
        unknown = set(value) - set(attribute.values)
        if unknown:
            raise ValueError(f"{where}: {sorted(unknown)} aren't values of the attribute, expected some of {list(attribute.values)}")
        return {label: float(c) for label, c in value.items()}
    if not labels and isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)
    expected = "a table of label -> coefficient" if labels else "a number"
    raise ValueError(f"{where}: expected {expected}, got {value!r}")


def _capacity(lane_id: str, value: object) -> int:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 1:
        return value
    raise ValueError(f"lanes.{lane_id}.capacity must be a whole number of at least 1, got {value!r}")


def _duration(task_id: str, spec: dict, attributes: dict[str, Distribution]) -> Duration:
    where = f"tasks.{task_id}.duration"
    spec = dict(spec)
    scale = spec.pop("scale", None)
    if set(spec) == {"fixed"}:
        base = FixedDuration(float(spec["fixed"]))
    elif set(spec) == {"triangular"}:
        low, mode, high = _triangular(where, spec["triangular"])
        if low < 0:
            raise ValueError(f"{where}: a duration can't be negative, got min {low}")
        base = Triangular(low, mode, high)
    else:
        raise ValueError(f"{where}: unsupported distribution {spec!r}")
    if scale is None:
        return base
    if not isinstance(scale, dict) or not scale:
        raise ValueError(f"{where}.scale: expected a table of attribute terms, got {scale!r}")
    coefficients = {name: _coefficient(f"{where}.scale.{name}", c, attributes.get(name)) for name, c in scale.items()}
    mean_factor = 1 + sum(_mean_term(c, attributes[name]) for name, c in coefficients.items())
    return ScaledDuration(base, coefficients, mean_factor)


def _mean_term(coefficient: float | dict[str, float], attribute: Distribution) -> float:
    """Mean of one attribute term over the attribute's distribution."""
    if isinstance(coefficient, dict):
        return sum(w * coefficient.get(v, 0.0) for v, w in zip(attribute.values, attribute.weights))
    match attribute:
        case Choice(values, weights):
            return coefficient * sum(w * v for v, w in zip(values, weights))
        case Poisson() | Triangular():
            return coefficient * attribute.mean
    raise TypeError(f"no mean for {attribute!r}")
