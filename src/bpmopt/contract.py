"""The JSON schema of the results file (schema/results.schema.json), the contract between the notebook and the page.

Kept apart from results.py so the catalog loader can check its entries against
the contract without importing the module that assembles the results file:
results depends on scenarios, and both depend on this module.
"""

import json
from functools import cache
from importlib import resources

import jsonschema


@cache
def validator() -> jsonschema.Draft202012Validator:
    schema = json.loads(resources.files("bpmopt").joinpath("schema/results.schema.json").read_text())
    # Formats like date-time are only checked with a format checker (needs rfc3339-validator).
    return jsonschema.Draft202012Validator(schema, format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER)


def validate_changes(changes: list[dict]) -> None:
    """Raise jsonschema.ValidationError if a change catalog breaks the contract's `changes` section.

    Lets the catalog loader catch a bad entry before any simulation runs.
    """
    schema = validator()
    section = schema.schema["properties"]["changes"]
    error = jsonschema.exceptions.best_match(schema.evolve(schema={**section, "$defs": schema.schema["$defs"]}).iter_errors(changes))
    if error is not None:
        raise error
