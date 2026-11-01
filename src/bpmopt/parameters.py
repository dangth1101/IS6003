"""Load the human-editable parameter file (TOML) that drives the simulator.

Time unit: working days on a continuous clock.
"""

import tomllib
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class FixedDuration:
    value: float

    def sample(self, rng: np.random.Generator) -> float:
        return self.value


Duration = FixedDuration


@dataclass(frozen=True)
class Parameters:
    version: str
    task_durations: dict[str, Duration]  # task ID -> duration


def load_parameters(path: str | Path) -> Parameters:
    with open(path, "rb") as f:
        raw = tomllib.load(f)
    durations = {task_id: _duration(task_id, entry["duration"]) for task_id, entry in raw.get("tasks", {}).items()}
    return Parameters(version=str(raw["version"]), task_durations=durations)


def _duration(task_id: str, spec: dict) -> Duration:
    if set(spec) == {"fixed"}:
        return FixedDuration(float(spec["fixed"]))
    raise ValueError(f"tasks.{task_id}.duration: unsupported distribution {spec!r}")
