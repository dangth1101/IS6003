"""Check a BPMN file against the book's modeling rules.

Book: Dumas et al., Fundamentals of BPM, 2nd ed. Page numbers are printed pages.

`lint(path)` returns a list of `Violation`s. An empty list means the model is
clean; our project models must have no errors and no warnings.

Rules (ID, severity, source):

- POOL         error    process and lanes sit inside a pool (§3.4)
- EVENT-LABEL  error    start/end events labeled object + past participle, not "Start"/"End" (§3.1 p.77, p.190)
- ARC-LABEL    error    no yes/no labels on XOR split arcs (§5.4.3 p.190)
- REACH        error    every node on a path from a start to an end event (§5.4.1 p.184)
- SUBSET       error    only start/end events, tasks, XOR and AND gateways
- G1           warning  no pass-through gateways (our interpretation, see the check)
- G2           warning  at most 5 routing paths per element (our threshold)
- G3           warning  one start per trigger, one end per outcome (partly heuristic)
- G4           error    split and join types match (structuredness, as far as detectable)
- G5           error    no OR gateways
- G6           warning  verb-object activity labels (heuristic)
- G7           warning  at most 30 flow nodes

The 7PMG are guidelines, i.e. suggestions (p.192), so most are warnings. G4
and G5 are errors because a mismatched split/join is a behavioral anomaly
(p.185) and an OR gateway is outside the subset the simulator can run.
"""

from dataclasses import dataclass
from pathlib import Path

from bpmopt.bpmn import ProcessModel, read_bpmn

ERROR = "error"
WARNING = "warning"


@dataclass(frozen=True)
class Violation:
    rule: str
    element_id: str
    message: str
    severity: str


def lint(path: str | Path) -> list[Violation]:
    model = read_bpmn(path)
    violations: list[Violation] = []
    for check in _CHECKS:
        violations.extend(check(model))
    return violations


def _check_pool(model: ProcessModel) -> list[Violation]:
    if model.pool is not None:
        return []
    return [
        Violation(
            "POOL",
            model.process_id,
            "Process has no pool. Put the process, and its lanes, inside a pool (§3.4).",
            ERROR,
        )
    ]


EVENT_TYPES = ("startEvent", "endEvent")

# Labels that name the event type instead of a business object. Vietnamese
# entries are there because the original as-is model uses them.
GENERIC_EVENT_LABELS = {"start", "end", "begin", "finish", "stop", "done", "bắt đầu", "kết thúc"}


def _check_event_labels(model: ProcessModel) -> list[Violation]:
    """Events are labeled object + past participle, e.g. "Invoice emitted" (§3.1 p.77, §5.4.3 p.190)."""
    violations = []
    for node in model.nodes.values():
        if node.element_type not in EVENT_TYPES:
            continue
        label = node.label
        if not label:
            problem = "has no label"
        elif label.lower() in GENERIC_EVENT_LABELS:
            problem = f'has the generic label "{label}"'
        elif len(label.split()) < 2:
            problem = f'label "{label}" has no business object'
        else:
            continue
        violations.append(
            Violation(
                "EVENT-LABEL",
                node.id,
                f"Event {problem}. Use business object + past participle, e.g. "
                '"Invoice emitted" (§3.1 p.77, §5.4.3 p.190).',
                ERROR,
            )
        )
    return violations


YES_NO_LABELS = {"yes", "no", "y", "n", "true", "false", "có", "không"}


def _check_arc_labels(model: ProcessModel) -> list[Violation]:
    """XOR split arcs carry explicit conditions, not yes/no (§5.4.3 p.190)."""
    violations = []
    for gateway in model.xor_splits():
        for arc in model.outgoing(gateway.id):
            if arc.label.strip(" ?!.").lower() in YES_NO_LABELS:
                violations.append(
                    Violation(
                        "ARC-LABEL",
                        arc.id,
                        f'XOR split arc labeled "{arc.label}". Use a condition that says what holds, '
                        'e.g. "plan acceptable" / "plan unacceptable" (§5.4.3 p.190).',
                        ERROR,
                    )
                )
    return violations


def _check_reachability(model: ProcessModel) -> list[Violation]:
    """Model-level rule: every flow node is on a path from a start to an end event (§5.4.1 p.184).

    This is a graph check. It catches dead activities and nodes that can never
    finish, but not every soundness problem (p.186): an AND-join fed by an
    XOR-split deadlocks yet passes here. G4 catches the common case of that.
    """
    successors, predecessors = _adjacency(model)
    from_start = _reachable([n.id for n in model.nodes_of_type("startEvent")], successors)
    to_end = _reachable([n.id for n in model.nodes_of_type("endEvent")], predecessors)
    violations = []
    for node_id in model.nodes:
        if node_id not in from_start:
            violations.append(
                Violation(
                    "REACH",
                    node_id,
                    "Element can't be reached from a start event, so it can never run (§5.4.1 p.184, p.186).",
                    ERROR,
                )
            )
        if node_id not in to_end:
            violations.append(
                Violation(
                    "REACH",
                    node_id,
                    "No path from this element to an end event, so the case can't complete (§5.4.1 p.184, p.186).",
                    ERROR,
                )
            )
    return violations


def _check_g1_few_elements(model: ProcessModel) -> list[Violation]:
    """G1: use as few model elements as possible (§5.4.4 p.192).

    Our interpretation: the book gives no number for G1, and model size is
    already G7's job. So G1 flags elements that can be removed without
    changing behavior: a gateway with one incoming and one outgoing arc.
    Such a gateway is neither a split nor a join, which §5.4.1 (p.184)
    also rules out.
    """
    successors, predecessors = _adjacency(model)
    return [
        Violation(
            "G1",
            node.id,
            "Gateway with one incoming and one outgoing arc does nothing; remove it. "
            "7PMG G1: use as few model elements as possible (§5.4.4 p.192).",
            WARNING,
        )
        for node in model.nodes.values()
        if node.element_type in GATEWAY_TYPES and len(successors[node.id]) == 1 and len(predecessors[node.id]) == 1
    ]


# Our threshold: the book gives none for G2 (p.192). 5 lets a split or join have
# up to 4 branches, the largest block we expect in our models.
MAX_ROUTING_PATHS = 5


def _check_g2_routing_paths(model: ProcessModel) -> list[Violation]:
    """G2: minimize the routing paths per element (§5.4.4 p.192).

    Routing paths = incoming + outgoing sequence flows of one flow node.
    """
    successors, predecessors = _adjacency(model)
    violations = []
    for node_id in model.nodes:
        paths = len(successors[node_id]) + len(predecessors[node_id])
        if paths > MAX_ROUTING_PATHS:
            violations.append(
                Violation(
                    "G2",
                    node_id,
                    f"{paths} routing paths (incoming + outgoing arcs), our limit is {MAX_ROUTING_PATHS}. "
                    "7PMG G2: minimize the routing paths per element (§5.4.4 p.192).",
                    WARNING,
                )
            )
    return violations


def _check_g3_one_event_per_outcome(model: ProcessModel) -> list[Violation]:
    """G3: one start event per trigger, one end event per outcome (§5.4.4 p.192).

    Two parts:
    - Events of the same kind with the same label are one trigger or outcome
      drawn twice (like the two "case closed" ends in Fig. 5.18, p.193).
    - Heuristic: one end event but an XOR split that isn't closed by an XOR
      join. Such a split decides between outcomes or loops back, and with one
      end event every case ends the same way. This is what catches a rejected
      proposal that can only loop back. It also fires on a plain rework loop,
      which is why it is a warning.
    """
    violations = []
    for kind, what in (("startEvent", "trigger"), ("endEvent", "outcome")):
        by_label: dict[str, list[str]] = {}
        for node in model.nodes_of_type(kind):
            if node.label:
                by_label.setdefault(node.label.lower(), []).append(node.id)
        for ids in by_label.values():
            if len(ids) > 1:
                violations.extend(
                    Violation(
                        "G3",
                        node_id,
                        f"{len(ids)} {kind}s share one label, so one {what} is drawn twice. "
                        f"7PMG G3: one start event per trigger, one end event per outcome (§5.4.4 p.192).",
                        WARNING,
                    )
                    for node_id in ids
                )

    ends = model.nodes_of_type("endEvent")
    if len(ends) == 1:
        ipdom = _immediate_post_dominators(model)
        open_splits = [
            g.id
            for g in model.xor_splits()
            if not (ipdom.get(g.id) in model.nodes and model.nodes[ipdom[g.id]].element_type == "exclusiveGateway")
        ]
        if open_splits:
            violations.append(
                Violation(
                    "G3",
                    ends[0].id,
                    f"Only one end event, but XOR split(s) {', '.join(open_splits)} aren't closed by an XOR join. "
                    "If a branch is its own outcome (e.g. a rejected request), give it its own end event. "
                    "7PMG G3: one end event per outcome (§5.4.4 p.192), and always end a model with an "
                    "end event (§3.2 p.81). Heuristic check.",
                    WARNING,
                )
            )
    return violations


GATEWAY_TYPES = {"exclusiveGateway", "parallelGateway", "inclusiveGateway"}


def _check_g4_structured(model: ProcessModel) -> list[Violation]:
    """G4: model as structured as possible (§5.4.4 p.192), as far as a graph check can tell.

    Our check: a split's branches should first meet again at a join of the
    same type. We find that meeting point as the split's immediate
    post-dominator. If it is a gateway of another type, the split and join
    don't match, which always gives a behavioral anomaly (§5.4.1 p.185):
    AND split + XOR join = lack of synchronization, XOR split + AND join =
    deadlock. That's why this is an error, not a warning. Unstructured
    cycles and splits whose branches never meet are not flagged.
    """
    ipdom = _immediate_post_dominators(model)
    violations = []
    for gateway in model.nodes.values():
        if gateway.element_type not in GATEWAY_TYPES or len(model.outgoing(gateway.id)) < 2:
            continue
        join = model.nodes.get(ipdom.get(gateway.id, ""))
        if join is None or join.element_type not in GATEWAY_TYPES or join.element_type == gateway.element_type:
            continue
        violations.append(
            Violation(
                "G4",
                gateway.id,
                f"{gateway.element_type} split is closed by {join.element_type} {join.id}. Mismatched split "
                "and join cause deadlock or lack of synchronization (§5.4.1 p.185). "
                "7PMG G4: model as structured as possible (§5.4.4 p.192).",
                ERROR,
            )
        )
    return violations


_EXIT = "__exit__"


def _immediate_post_dominators(model: ProcessModel) -> dict[str, str]:
    """Node ID -> its immediate post-dominator: the nearest node every path to an end passes.

    All end events feed one virtual exit. Nodes that can't reach an end get no entry.
    """
    successors, predecessors = _adjacency(model)
    ends = [n.id for n in model.nodes_of_type("endEvent")]
    live = _reachable(ends, predecessors)
    succ = {n: [s for s in successors[n] if s in live] for n in live}
    for end in ends:
        succ[end] = [_EXIT]
    everything = live | {_EXIT}
    pdom: dict[str, set[str]] = {n: set(everything) for n in live}
    pdom[_EXIT] = {_EXIT}
    changed = True
    while changed:
        changed = False
        for n in live:
            new = {n} | set.intersection(*(pdom[s] for s in succ[n]))
            if new != pdom[n]:
                pdom[n] = new
                changed = True
    # The nearest strict post-dominator is the one with the most post-dominators of its own.
    return {n: max(pdom[n] - {n}, key=lambda d: len(pdom[d])) for n in live}


def _adjacency(model: ProcessModel) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    successors: dict[str, list[str]] = {node_id: [] for node_id in model.nodes}
    predecessors: dict[str, list[str]] = {node_id: [] for node_id in model.nodes}
    for flow in model.flows.values():
        if flow.source in model.nodes and flow.target in model.nodes:
            successors[flow.source].append(flow.target)
            predecessors[flow.target].append(flow.source)
    return successors, predecessors


def _reachable(roots: list[str], edges: dict[str, list[str]]) -> set[str]:
    seen = set(roots)
    stack = list(roots)
    while stack:
        for nxt in edges[stack.pop()]:
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return seen


SUPPORTED_TYPES = {"startEvent", "endEvent", "task", "exclusiveGateway", "parallelGateway"}


def _check_subset(model: ProcessModel) -> list[Violation]:
    """Only the element types the simulator runs: the core of §3.1–3.2 (events, tasks, XOR/AND gateways)."""
    return [
        Violation(
            "SUBSET",
            node.id,
            f"{node.element_type} is outside the supported subset: start and end events, tasks, "
            "XOR and AND gateways (§3.1–3.2).",
            ERROR,
        )
        for node in model.nodes.values()
        # OR gateways are reported by G5 instead, so one problem gives one violation.
        if node.element_type not in SUPPORTED_TYPES and node.element_type != "inclusiveGateway"
    ]


def _check_g5_no_or_gateways(model: ProcessModel) -> list[Violation]:
    """G5: avoid OR gateways where possible (§5.4.4 p.193).

    An error, not a warning: OR gateways are also outside our subset, so the
    simulator can't run them.
    """
    return [
        Violation(
            "G5",
            node.id,
            "OR gateway. 7PMG G5: avoid OR gateways, use XOR or AND (§5.4.4 p.193). "
            "Also outside the supported subset.",
            ERROR,
        )
        for node in model.nodes_of_type("inclusiveGateway")
    ]


# Imperative verbs that pass the G6 heuristic. Extend this list when a model
# uses a real verb that isn't here yet.
KNOWN_VERBS = {
    "accept", "adjust", "analyse", "analyze", "approve", "archive", "assess", "assign", "audit",
    "build", "calculate", "call", "check", "close", "code", "collect", "configure", "confirm",
    "correct", "create", "decide", "define", "deliver", "deploy", "design", "develop", "document",
    "draft", "estimate", "evaluate", "file", "fix", "get", "go", "hand", "hold", "implement",
    "improve", "inform", "inspect", "install", "integrate", "issue", "launch", "log", "measure",
    "merge", "migrate", "monitor", "notify", "open", "operate", "pay", "plan", "prepare",
    "prioritise", "prioritize", "record", "refine", "register", "reject", "release", "renew",
    "repair", "report", "request", "resolve", "review", "revise", "run", "schedule", "send", "ship",
    "sign", "specify", "start", "store", "submit", "test", "train", "update", "validate", "verify",
    "write",
}  # fmt: skip

# "General verbs like 'to make', 'to do', 'to perform', or 'to conduct' should be
# replaced with meaningful verbs" (§3.1 p.77).
GENERAL_VERBS = {"make", "do", "perform", "conduct"}


def _check_g6_activity_labels(model: ProcessModel) -> list[Violation]:
    """G6: use verb-object activity labels (§5.4.4 p.193, §3.1 p.77).

    This is a heuristic, not grammar parsing, so it reports warnings. A label
    passes when it starts with a capitalized verb from KNOWN_VERBS, the verb
    isn't a general one, and an object follows. It is English only.
    """
    violations = []
    for task in model.nodes_of_type("task"):
        words = task.label.split()
        first = words[0].lower() if words else ""
        if not words:
            problem = "has no label"
        elif first in GENERAL_VERBS:
            problem = f'starts with the general verb "{words[0]}"'
        elif first not in KNOWN_VERBS:
            problem = f'doesn\'t start with a known imperative verb ("{words[0]}")'
        elif len(words) < 2:
            problem = "has a verb but no business object"
        elif not words[0][0].isupper():
            problem = "doesn't start with a capital letter"
        else:
            continue
        violations.append(
            Violation(
                "G6",
                task.id,
                f'Activity label "{task.label}" {problem}. 7PMG G6: use verb-object labels, '
                'e.g. "Inform complainant" (§5.4.4 p.193, §3.1 p.77). Heuristic check.',
                WARNING,
            )
        )
    return violations


# G7's threshold is the book's own number (p.193).
MAX_ELEMENTS = 30


def _check_g7_model_size(model: ProcessModel) -> list[Violation]:
    """G7: decompose a model with more than 30 elements (§5.4.4 p.193).

    Our interpretation: the book doesn't define "element". We count flow nodes
    (events, tasks, gateways). Arcs are left out because their number follows
    from the nodes, and the pool and lanes are left out because they don't
    add control flow.
    """
    count = len(model.nodes)
    if count <= MAX_ELEMENTS:
        return []
    return [
        Violation(
            "G7",
            model.process_id,
            f"Model has {count} flow nodes. 7PMG G7: decompose a model with more than "
            f"{MAX_ELEMENTS} elements (§5.4.4 p.193). We count events, tasks and gateways.",
            WARNING,
        )
    ]


_CHECKS = [
    _check_pool,
    _check_event_labels,
    _check_arc_labels,
    _check_reachability,
    _check_subset,
    _check_g1_few_elements,
    _check_g2_routing_paths,
    _check_g3_one_event_per_outcome,
    _check_g4_structured,
    _check_g5_no_or_gateways,
    _check_g6_activity_labels,
    _check_g7_model_size,
]
