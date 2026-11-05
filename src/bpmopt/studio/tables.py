"""Helpers on the parameter file's tables (the dicts the page sends)."""

from bpmopt.parameters import PER_ELEMENT, entry_key


def without_rationales(value):
    """A parameter dict or entry without its rationales: what the simulation uses."""
    if isinstance(value, dict):
        return {key: without_rationales(item) for key, item in value.items() if key != "rationale"}
    if isinstance(value, list):
        return [without_rationales(item) for item in value]
    return value


def by_entry(params: dict) -> dict:
    """The tables flattened to entry name ("tasks.<id>", "arrivals", "version", ...) -> value without rationale."""
    out = {}
    for section, value in params.items():
        if section in PER_ELEMENT:
            out |= {entry_key(section, element_id): without_rationales(entry) for element_id, entry in value.items()}
        else:
            out[section] = without_rationales(value)
    return out
