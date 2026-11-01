"""Load the human-editable parameter file (TOML) that drives the simulator.

Time unit: working days on a continuous clock.
"""

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class FixedDuration:
    value: float

    @property
    def mean(self) -> float:
        return self.value

    def sample(self, rng: np.random.Generator) -> float:
        return self.value


Duration = FixedDuration


@dataclass(frozen=True)
class Parameters:
    version: str
    task_durations: dict[str, Duration]  # task ID -> duration
    arrival_rate: float | None = None  # cases per working day (Poisson); None: every case arrives at time 0
    lane_capacities: dict[str, int] = field(default_factory=dict)  # lane ID -> resources; a lane not listed is unlimited
    warm_up: float = 0.0  # working days; cases arriving before this are simulated but left out of the log
    # XOR-split ID -> {outgoing flow ID -> branching probability (book p.257)}. Fixed for now; ticket 07 adds
    # probabilities that depend on case attributes.
    branch_probabilities: dict[str, dict[str, float]] = field(default_factory=dict)


def load_parameters(path: str | Path) -> Parameters:
    with open(path, "rb") as f:
        raw = tomllib.load(f)
    durations = {task_id: _duration(task_id, entry["duration"]) for task_id, entry in raw.get("tasks", {}).items()}
    arrival_rate = float(raw["arrivals"]["rate"]) if "arrivals" in raw else None
    if arrival_rate is not None and arrival_rate <= 0:
        raise ValueError(f"arrivals.rate must be positive, got {arrival_rate}")
    warm_up = float(raw["warm_up"]["length"]) if "warm_up" in raw else 0.0
    if warm_up < 0:
        raise ValueError(f"warm_up.length must not be negative, got {warm_up}")
    if warm_up > 0 and arrival_rate is None:
        raise ValueError("warm_up needs an arrival rate: without [arrivals] every case arrives at time 0")
    capacities = {lane_id: _capacity(lane_id, entry["capacity"]) for lane_id, entry in raw.get("lanes", {}).items()}
    branches = {gateway_id: _branches(gateway_id, entry["branches"]) for gateway_id, entry in raw.get("gateways", {}).items()}
    return Parameters(
        version=str(raw["version"]),
        task_durations=durations,
        arrival_rate=arrival_rate,
        lane_capacities=capacities,
        warm_up=warm_up,
        branch_probabilities=branches,
    )


def _branches(gateway_id: str, spec: dict) -> dict[str, float]:
    probabilities = {flow_id: float(p) for flow_id, p in spec.items()}
    if any(not 0 <= p <= 1 for p in probabilities.values()) or abs(sum(probabilities.values()) - 1) > 1e-9:
        raise ValueError(f"gateways.{gateway_id}.branches: probabilities must lie in [0, 1] and sum to 1, got {spec!r}")
    return probabilities


def _capacity(lane_id: str, value: object) -> int:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 1:
        return value
    raise ValueError(f"lanes.{lane_id}.capacity must be a whole number of at least 1, got {value!r}")


def _duration(task_id: str, spec: dict) -> Duration:
    if set(spec) == {"fixed"}:
        return FixedDuration(float(spec["fixed"]))
    raise ValueError(f"tasks.{task_id}.duration: unsupported distribution {spec!r}")
