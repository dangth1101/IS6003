"""The suggestions panel: the change catalog C1-C4 on the as-is preset.

The preset is passed in as `preset`, a dict of file name -> text: the as-is
model and parameters, the change catalog and its model files (the worker
fetches them from web/studio/presets/, copied from models/).
"""

import tomllib
from collections.abc import Mapping

from bpmopt.bpmn import parse_bpmn
from bpmopt.parameters import parse_parameters
from bpmopt.scenarios import Catalog, model_combo, parse_catalog
from bpmopt.studio.errors import StudioError
from bpmopt.studio.tables import without_rationales

PRESET_MODEL = "as_is.bpmn"
PRESET_PARAMS = "as_is.params.toml"
PRESET_CATALOG = "to_be.catalog.toml"


def apply_suggestion(xml: str, change_ids: list[str], preset: Mapping[str, str]) -> dict:
    """The as-is preset with exactly these catalog changes applied: {xml, params, changes}.

    xml is the current model. It must be the preset's model with some set of
    structural changes (any catalog scenario's model), or StudioError
    "hand_edited": after a hand edit suggestions no longer apply. The result
    doesn't build on the current parameters: it is the catalog's scenario, the
    model file of its structural changes and its parameter tables
    (Catalog.scenario_tables). So applying a set again, or a smaller one, is
    the undo. changes lists the applied IDs in catalog order. An ID the
    catalog lacks is refused ("unknown_changes", data changes and catalog).
    """
    design = _Preset(preset)
    if parse_bpmn(xml) not in design.models():
        raise StudioError("hand_edited", "the model was edited by hand, so the suggestions no longer apply to it; go back to the preset to use them")
    ids = design.catalog.ids
    unknown = sorted(set(change_ids) - set(ids))
    if unknown:
        raise StudioError("unknown_changes", f"no changes {', '.join(unknown)} in the catalog, which has {', '.join(ids)}", changes=unknown, catalog=ids)
    combo = [change.id for change in design.catalog.changes_in(change_ids)]
    xml_out, params = design.scenario(combo)
    return {"xml": xml_out, "params": params, "changes": combo}


def suggestions(xml: str, preset: Mapping[str, str], params: dict | None = None) -> dict:
    """The change catalog for the suggestions panel, and what the current design is.

    changes: the catalog's changes in order, each {id, title, driver, heuristic
    {name, ref}, expected_effect, trade_off {time, cost, quality, flexibility,
    note}}, as in the results file. available: whether xml is the preset's model
    with some set of structural changes, so apply_suggestion accepts it.

    With the current params (the panel's), also: applied, the changes the design
    carries in catalog order (a structural one when the model has it, a
    parameter one while every entry it overrides has the catalog's values), and
    exact, whether params are the catalog's for that set, so applying or undoing
    loses no value set by hand. Rationales are not compared. Both are None when
    the suggestions aren't available or params isn't given.
    """
    design = _Preset(preset)
    model = parse_bpmn(xml)
    matches = [combo for combo, (scenario_model, _) in design.catalog.scenarios.items() if scenario_model == model]
    applied = exact = None
    if matches and params is not None:
        structural = design.structural_ids()
        carried = matches[0] & structural  # every scenario on this model has the same structural changes
        applied = [
            change.id
            for change in design.catalog.changes
            if change.id in carried or (change.id not in structural and _carries(params, change.overrides))
        ]
        _, expected = design.scenario(applied)
        exact = without_rationales(params) == without_rationales(expected)
    return {"changes": design.catalog.entries(), "available": bool(matches), "applied": applied, "exact": exact}


class _Preset:
    """The preset's catalog, resolved, with the raw tables it was read from."""

    def __init__(self, files: Mapping[str, str]):
        self.files = files
        self.params = tomllib.loads(files[PRESET_PARAMS])
        raw_catalog = tomllib.loads(files[PRESET_CATALOG])
        self.model_files = {model_combo(key): file for key, file in raw_catalog.get("models", {}).items()}
        model = parse_bpmn(files[PRESET_MODEL])
        models = {file: parse_bpmn(files[file]) for file in self.model_files.values()}
        self.catalog: Catalog = parse_catalog(raw_catalog, models, model=model, params=parse_parameters(self.params, model), where=PRESET_CATALOG)

    def models(self) -> list:
        return [model for model, _ in self.catalog.scenarios.values()]

    def structural_ids(self) -> set[str]:
        return set().union(*self.model_files)

    def scenario(self, combo: list[str]) -> tuple[str, dict]:
        """The model text and parameter tables of the catalog scenario combo."""
        structural = frozenset(combo) & self.structural_ids()
        xml = self.files[self.model_files[structural]] if structural else self.files[PRESET_MODEL]
        return xml, self.catalog.scenario_tables(self.params, combo)


def _carries(params: dict, overrides: dict) -> bool:
    """Whether every entry the overrides set has their values in params."""
    return all(
        without_rationales(params.get(section, {}).get(element_id)) == without_rationales(entry)
        for section, entries in overrides.items()
        for element_id, entry in entries.items()
    )
