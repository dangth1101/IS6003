"""Planted attribute effects: what the synthetic log should let the ML find.

The log is synthetic, so every attribute effect in it was put into the
parameter file on purpose. A planted effects file (TOML) lists them, so the
ML drivers can be checked against the truth:

    negative_control = "requesting_unit"   # an attribute nothing reads

    [[effects]]
    element = "Task_BuildApplication"      # a task or an XOR-split
    attribute = "complexity"
    kind = "duration"                      # scaled duration, or "branch" for a logistic branch

The loader checks the file against the parameters both ways, so it can't
drift from what is simulated.
"""

import tomllib
from dataclasses import dataclass
from pathlib import Path

from bpmopt.bpmn import ProcessModel
from bpmopt.flow_analysis import loop_back_flows
from bpmopt.parameters import Logistic, Parameters, ScaledDuration

Effect = tuple[str, str, str]  # element ID, attribute, kind


@dataclass(frozen=True)
class PlantedEffects:
    effects: tuple[Effect, ...]
    negative_control: str

    def expected_drivers(self, model: ProcessModel) -> dict[str, list[str]]:
        """ML task ID -> the planted attributes it should rank high, in file order.

        Every effect lengthens some cases, so the cycle time task should find
        all planted attributes. A rework task should find only the attributes
        of its own gateway's branch; a gateway without any gets an empty list.
        """
        expected = {"cycle_time": _unique(attribute for _, attribute, _ in self.effects)}
        for gateway_id in loop_back_flows(model):
            expected[f"rework_{gateway_id}"] = _unique(a for element, a, kind in self.effects if element == gateway_id and kind == "branch")
        return expected


def planted_in(params: Parameters) -> set[Effect]:
    """Every attribute term in the parameters: scaled durations and logistic branches."""
    effects = {
        (task_id, name, "duration")
        for task_id, duration in params.task_durations.items()
        if isinstance(duration, ScaledDuration)
        for name in duration.coefficients
    }
    for gateway_id, branches in params.branch_probabilities.items():
        for p in branches.flows.values():
            if isinstance(p, Logistic):
                effects |= {(gateway_id, name, "branch") for name in p.coefficients}
    return effects


def load_planted_effects(path: str | Path, params: Parameters) -> PlantedEffects:
    """Read a planted effects file. Raises ValueError unless it lists exactly the effects in params."""
    path = Path(path)
    with path.open("rb") as f:
        raw = tomllib.load(f)
    effects = tuple((e["element"], e["attribute"], e["kind"]) for e in raw.get("effects", []))
    negative_control = raw.get("negative_control")

    actual = planted_in(params)
    problems = [f"{e[0]}.{e[1]} ({e[2]}): in the parameters, not in the file" for e in sorted(actual - set(effects))]
    problems += [f"{e[0]}.{e[1]} ({e[2]}): in the file, not in the parameters" for e in sorted(set(effects) - actual)]
    if len(set(effects)) != len(effects):
        problems.append("an effect is listed twice")
    if negative_control not in params.attributes:
        problems.append(f"negative control {negative_control!r} isn't an attribute in the parameters")
    elif any(attribute == negative_control for _, attribute, _ in actual):
        problems.append(f"negative control {negative_control!r} has an effect in the parameters")
    if problems:
        raise ValueError(f"{path.name} doesn't match the parameters:\n  " + "\n  ".join(problems))
    return PlantedEffects(effects, negative_control)


def _unique(items) -> list[str]:
    return list(dict.fromkeys(items))
