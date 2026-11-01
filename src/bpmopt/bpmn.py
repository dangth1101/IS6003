"""Read a BPMN 2.0 file into an in-memory process model.

The reader is faithful: it keeps every flow node with its BPMN element type,
even ones the simulator can't execute. Deciding what is supported is up to the
consumer (the simulator raises, the linter reports).
"""

from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

BPMN_NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"

# Children of <process> that are not flow nodes.
_NOT_FLOW_NODES = {"laneSet", "sequenceFlow", "textAnnotation", "association", "documentation", "extensionElements"}


@dataclass(frozen=True)
class Node:
    id: str
    element_type: str  # BPMN element type, e.g. "task", "startEvent", "exclusiveGateway"
    label: str
    lane: str | None  # lane ID


@dataclass(frozen=True)
class Flow:
    id: str
    source: str
    target: str
    label: str


@dataclass(frozen=True)
class ProcessModel:
    process_id: str
    pool: str | None  # pool (participant) name, None if the process has no pool
    lanes: dict[str, str]  # lane ID -> lane name
    nodes: dict[str, Node]
    flows: dict[str, Flow]

    def outgoing(self, node_id: str) -> list[Flow]:
        return [f for f in self.flows.values() if f.source == node_id]

    def nodes_of_type(self, element_type: str) -> list[Node]:
        return [n for n in self.nodes.values() if n.element_type == element_type]


def read_bpmn(path: str | Path) -> ProcessModel:
    root = ElementTree.parse(path).getroot()
    processes = root.findall(_q("process"))
    if len(processes) != 1:
        raise ValueError(f"{path}: expected exactly one process, found {len(processes)}")
    process = processes[0]
    process_id = process.attrib["id"]

    pool = None
    for participant in root.iter(_q("participant")):
        if participant.get("processRef") == process_id:
            pool = _label(participant)

    lanes: dict[str, str] = {}
    lane_of: dict[str, str] = {}
    for lane in process.iter(_q("lane")):
        lanes[lane.attrib["id"]] = _label(lane)
        for ref in lane.findall(_q("flowNodeRef")):
            lane_of[(ref.text or "").strip()] = lane.attrib["id"]

    nodes: dict[str, Node] = {}
    flows: dict[str, Flow] = {}
    for el in process:
        element_type = _local(el.tag)
        if element_type == "sequenceFlow":
            flows[el.attrib["id"]] = Flow(el.attrib["id"], el.attrib["sourceRef"], el.attrib["targetRef"], _label(el))
        elif element_type not in _NOT_FLOW_NODES:
            node_id = el.attrib["id"]
            nodes[node_id] = Node(node_id, element_type, _label(el), lane_of.get(node_id))

    return ProcessModel(process_id, pool, lanes, nodes, flows)


def _q(tag: str) -> str:
    return f"{{{BPMN_NS}}}{tag}"


def _local(tag: str) -> str:
    return tag.split("}", 1)[-1]


def _label(el: ElementTree.Element) -> str:
    # Modelers often wrap names over several lines; collapse that whitespace.
    return " ".join(el.get("name", "").split())
