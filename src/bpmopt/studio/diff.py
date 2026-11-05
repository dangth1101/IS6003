"""What changed from one design to the next, so the page can outline it in the diagram."""

from bpmopt.bpmn import ProcessModel, parse_bpmn
from bpmopt.parameters import PER_ELEMENT, split_entry
from bpmopt.studio.tables import by_entry


def diff_designs(before_xml: str, before_params: dict, after_xml: str, after_params: dict) -> dict:
    """What changed from one design to the next: {added, removed, rerouted, parameters}.

    added and removed are the nodes and flows only one model has, rerouted the
    flows both have with another source or target, each as {id, label} in model
    order (removed in the old model's). parameters are the entry names
    ("tasks.<id>", "lanes.<id>", "arrivals", ...) whose values differ,
    rationales not compared, leaving out entries of removed elements. Layout
    (diagram positions) is not part of the model, so moving shapes changes nothing.
    """
    before, after = parse_bpmn(before_xml), parse_bpmn(after_xml)
    old, new = _elements(before), _elements(after)
    rerouted = [
        _row(flow)
        for flow_id, flow in after.flows.items()
        if flow_id in before.flows and (before.flows[flow_id].source, before.flows[flow_id].target) != (flow.source, flow.target)
    ]
    old_entries, new_entries = by_entry(before_params), by_entry(after_params)
    keys = [*new_entries, *(key for key in old_entries if key not in new_entries)]
    present = set(new) | set(after.lanes)

    def kept(key: str) -> bool:
        section, element_id = split_entry(key)
        return section not in PER_ELEMENT or element_id in present

    return {
        "added": [_row(element) for element_id, element in new.items() if element_id not in old],
        "removed": [_row(element) for element_id, element in old.items() if element_id not in new],
        "rerouted": rerouted,
        "parameters": [key for key in keys if old_entries.get(key) != new_entries.get(key) and kept(key)],
    }


def _elements(model: ProcessModel) -> dict:
    return {**model.nodes, **model.flows}


def _row(element) -> dict:
    return {"id": element.id, "label": element.label}
