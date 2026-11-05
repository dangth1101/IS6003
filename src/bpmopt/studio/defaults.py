"""A full parameter set for any model, and the edits the parameter panel makes to it.

Defaults for a new or imported model (default_parameters). Every one is an
assumption the page shows, so the user can replace it with an estimate.

- Task duration triangular [1, 2, 4] working days: a short task of about two
  days that sometimes takes twice that. Same shape as the shortest as-is tasks
  (code review, plan approval), so a new task doesn't dominate the cycle time.
- XOR split: every outgoing flow equally likely. Nothing says one branch is
  more common, and equal shares are the easiest to see and change.
- Lane capacity 1: one person per lane, so a lane's tasks queue for them.
  The smallest real lane; raise it to the lane's head count.
- Arrival rate: the rate that keeps the busiest lane 80% busy (rho = rate x
  work per case / capacity, Eq. 7.8 p.270). Busy enough that waiting shows in
  the results, far enough below 1 that the queues settle (p.276). The as-is
  preset's busiest lane is at 0.87. Work per case comes from a 1,000-case pilot
  run without queues (seed 0), so loops and parallel branches count.
  Rounded to 3 significant digits.
- Warm-up: the time 100 cases take to arrive (100 / rate, whole days), so the
  queues fill from the empty start before cases are measured. Costs 10% more
  simulation at the default 1,000 cases. Only set together with a default rate.
- No default cycle time cut-off (cycles end at the end events) and no case
  attributes: those only come from an imported parameter file.

An entry is a default when its rationale starts with STUDIO_DEFAULT, so it
stays marked when the page sends the parameters back, and stops being one
once the page gives an edited entry its own rationale (STUDIO_EDIT).
"""

import copy
from dataclasses import replace

import numpy as np

from bpmopt.analysis import work_per_case
from bpmopt.bpmn import ProcessModel, parse_bpmn
from bpmopt.lint import ERROR, lint_model
from bpmopt.parameters import PER_ELEMENT, Logistic, ParameterError, element_ids, entry_key, parse_parameters, split_entry
from bpmopt.simulation import simulate
from bpmopt.studio.errors import ERROR_CODES, StudioError

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

# The rationale of an entry the user set in the parameter panel. It doesn't start with
# STUDIO_DEFAULT, so the entry stops being shown as a default.
STUDIO_EDIT = "Set in the studio."
# The single entries the panel sets; per element it sets tasks, gateways and lanes (PER_ELEMENT).
SETTABLE = ("arrivals", "warm_up", "cycle_time")

# "Reset to fixed": a logistic branch's share is its mean probability over this many cases.
RESET_CASES = 10_000
RESET_SEED = 0
RESET_RATIONALE = (
    f"Logistic branches replaced by their mean probability over {RESET_CASES:,} cases "
    f"drawn from the case attributes (seed {RESET_SEED}), so the overall rate stays about the same."
)


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
    known = element_ids(model)
    flows = {gateway_id: [flow.id for flow in model.outgoing(gateway_id)] for gateway_id in known["gateways"]}

    dropped = []
    for section in PER_ELEMENT:
        for element_id in list(raw.get(section, {})):
            stale = section == "gateways" and element_id in flows and set(raw[section][element_id].get("branches", {})) != set(flows[element_id])
            if element_id not in known[section] or stale:
                del raw[section][element_id]
                dropped.append(entry_key(section, element_id))
    if "cycle_time" in raw and raw["cycle_time"].get("ends_at") not in known["tasks"]:
        del raw["cycle_time"]
        dropped.append(entry_key("cycle_time"))

    def fill(section: str, element_id: str, key: str, value) -> None:
        entries = raw.setdefault(section, {})
        if element_id not in entries:
            entries[element_id] = {key: value, "rationale": f"{STUDIO_DEFAULT} {_RATIONALES[section]}"}

    for lane_id in known["lanes"]:
        fill("lanes", lane_id, "capacity", DEFAULT_CAPACITY)
    for task_id in known["tasks"]:
        fill("tasks", task_id, "duration", {"triangular": list(DEFAULT_DURATION)})
    for gateway_id in known["gateways"]:
        fill("gateways", gateway_id, "branches", {flow_id: 1 / len(flows[gateway_id]) for flow_id in flows[gateway_id]})
    raw = {section: value for section, value in raw.items() if value != {} or section not in PER_ELEMENT}
    if "arrivals" not in raw and not any(v.severity == ERROR for v in lint_model(model)):
        _fill_arrivals(raw, model)

    entries = [(section, None) for section in ("arrivals", "warm_up", "cycle_time")] + [
        (section, element_id) for section in ("attributes", *PER_ELEMENT) for element_id in raw.get(section, {})
    ]
    defaults = [
        entry_key(section, element_id)
        for section, element_id in entries
        if section in raw and (raw[section] if element_id is None else raw[section][element_id]).get("rationale", "").startswith(STUDIO_DEFAULT)
    ]
    return {"params": raw, "defaults": defaults, "dropped": dropped}


def _fill_arrivals(raw: dict, model: ProcessModel) -> None:
    """Set [arrivals] (and [warm_up], if missing) so the busiest limited lane runs at TARGET_UTILISATION."""
    pilot = parse_parameters({key: value for key, value in raw.items() if key != "warm_up"}, model)
    work = work_per_case(simulate(model, replace(pilot, lane_capacities={}), n_cases=PILOT_CASES, seed=PILOT_SEED))
    room = {lane_id: c / work[lane_id] for lane_id, c in pilot.lane_capacities.items() if work.get(lane_id, 0) > 0}
    if not room:
        return
    busiest = min(room, key=room.get)
    rate = float(f"{TARGET_UTILISATION * room[busiest]:.3g}")
    reason = _RATIONALES["arrivals"].format(lane=model.lanes[busiest] or busiest, target=TARGET_UTILISATION, cases=PILOT_CASES)
    raw["arrivals"] = {"rate": rate, "rationale": f"{STUDIO_DEFAULT} {reason}"}
    if "warm_up" not in raw:
        raw["warm_up"] = {"length": round(WARM_UP_CASES / rate), "rationale": f"{STUDIO_DEFAULT} {_RATIONALES['warm_up'].format(cases=WARM_UP_CASES)}"}


def set_parameter(xml: str, params: dict, entry: str, fields: dict) -> dict:
    """The parameters with one entry set from the parameter panel: {params, defaults, dropped}.

    entry is "tasks.<id>", "gateways.<id>" (an XOR split), "lanes.<id>",
    "arrivals", "warm_up" or "cycle_time"; fields its value as in the
    parameter file, e.g. {"duration": {"triangular": [1, 2, 4]}}, {"capacity": 2}
    or {"ends_at": "Task_X"}. {"ends_at": None} ends the cycle time at the end
    events again (no [cycle_time]). The entry is replaced by fields with the
    rationale STUDIO_EDIT, followed by fields' own rationale if it has one
    (fixed_branches gives one), so it is no longer a default; every other entry
    stays as it is. The result is completed by default_parameters and checked
    against the model. A StudioError with data {entry} refuses an invalid
    value (code: the parameter rule it breaks, or invalid_value), an element
    the model lacks (unknown_element; not_a_task, with task, for a cut-off) or
    an entry the panel doesn't set (not_settable).
    """
    model = parse_bpmn(xml)
    raw = copy.deepcopy(params)
    section, element_id = split_entry(entry)
    known = element_ids(model)
    own = fields.get("rationale")
    value = {**{k: v for k, v in fields.items() if k != "rationale"}, "rationale": f"{STUDIO_EDIT} {own}" if own else STUDIO_EDIT}
    if section == "cycle_time" and element_id is None and fields.get("ends_at") is None:
        raw.pop("cycle_time", None)
    elif section == "cycle_time" and element_id is None and fields["ends_at"] not in known["tasks"]:
        raise StudioError("not_a_task", f"cycle_time.ends_at: {fields['ends_at']} is not a task of the model", entry=entry, task=fields["ends_at"])
    elif section in SETTABLE and element_id is None:
        raw[section] = value
    elif section in PER_ELEMENT and element_id:
        if element_id not in known[section]:
            raise StudioError("unknown_element", f"{entry}: the model has no such element", entry=entry)
        raw.setdefault(section, {})[element_id] = value
    else:
        raise StudioError("not_settable", f"{entry}: the studio sets only {', '.join(SETTABLE)} and tasks, gateways or lanes by ID", entry=entry)
    try:
        filled = default_parameters(xml, raw)
        parse_parameters(filled["params"], model)
    except ParameterError as e:
        raise StudioError(e.rule if e.rule in ERROR_CODES else "invalid_value", str(e), entry=entry) from e
    except ValueError as e:
        raise StudioError("invalid_value", str(e), entry=entry) from e
    return filled


def fixed_branches(params: dict, gateway_id: str) -> dict:
    """The XOR split's branches with each logistic branch replaced by a fixed share ("reset to fixed").

    The share is the branch's mean probability over the case attributes
    (RESET_CASES cases drawn from the attribute distributions, seed RESET_SEED),
    rounded to 3 decimals, so the split keeps about the same overall rate but
    no longer depends on the attributes. Fixed and "rest" branches stay as they
    are. Returns {branches}, plus rationale (RESET_RATIONALE) when a branch was
    replaced: pass it to set_parameter as the fields.
    """
    parsed = parse_parameters(params)
    rng = np.random.default_rng(RESET_SEED)
    cases = [{name: d.sample(rng) for name, d in parsed.attributes.items()} for _ in range(RESET_CASES)]
    branches = dict(params["gateways"][gateway_id]["branches"])
    logistic = {flow_id: p for flow_id, p in parsed.branch_probabilities[gateway_id].flows.items() if isinstance(p, Logistic)}
    for flow_id, p in logistic.items():
        branches[flow_id] = round(float(np.mean([p.probability(case) for case in cases])), 3)
    return {"branches": branches, "rationale": RESET_RATIONALE} if logistic else {"branches": branches}
