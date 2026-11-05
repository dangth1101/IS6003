"""Write the parameter tables back as a parameter file, for the studio's export.

Pyodide has tomllib but no TOML writer, hence this one; it only needs the
types a parameter file holds.
"""

import json

EXPORT_HEADER = "# Parameter file exported from the simulation studio. Read it with bpmopt.parameters.load_parameters.\n"


def params_to_toml(params: dict) -> str:
    """The parameter dict as a parameter file: TOML that load_parameters reads back to the same tables.

    Laid out like the hand-written files: top-level keys first, then one
    [section] per single entry and one [section.id] per entry of a collection,
    each value on one line (tables inline).
    """
    lines = [EXPORT_HEADER.rstrip("\n")]
    lines += [f"{_toml_key(key)} = {_toml_value(value)}" for key, value in params.items() if not isinstance(value, dict)]
    for section, value in params.items():
        if not isinstance(value, dict):
            continue
        if value and all(isinstance(entry, dict) for entry in value.values()):
            tables = [(f"{_toml_key(section)}.{_toml_key(key)}", entry) for key, entry in value.items()]
        else:
            tables = [(_toml_key(section), value)]
        for header, table in tables:
            lines += ["", f"[{header}]", *(f"{_toml_key(key)} = {_toml_value(v)}" for key, v in table.items())]
    return "\n".join(lines) + "\n"


def _toml_key(key: str) -> str:
    return key if key and all(c.isascii() and (c.isalnum() or c in "_-") for c in key) else json.dumps(key, ensure_ascii=False)


def _toml_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)  # shortest text that reads back to the same float; inf and nan are TOML too
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)  # a JSON string is a valid TOML basic string
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(v) for v in value) + "]"
    if isinstance(value, dict):
        return "{ " + ", ".join(f"{_toml_key(k)} = {_toml_value(v)}" for k, v in value.items()) + " }" if value else "{}"
    raise TypeError(f"can't write {value!r} to a parameter file")
