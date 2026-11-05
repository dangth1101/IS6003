"""Read what the user imports or draws: a BPMN document (with the book's lint rules) and a parameter file."""

import re
import tomllib
from xml.etree import ElementTree

from bpmopt.bpmn import parse_bpmn
from bpmopt.lint import lint_model
from bpmopt.studio.errors import StudioError

_TOML_AT = re.compile(r"at line (\d+), column (\d+)")


def lint_xml(xml: str) -> list[dict]:
    """The book's lint rules on a BPMN string: the same violations, in the same order, as lint on its file.

    Each is {rule, severity ("error" or "warning"), element_id, message}. A
    document that isn't one readable BPMN process raises a StudioError, whose
    message starts "Not a readable BPMN document": unreadable_xml {line,
    column}, unreadable_attribute {attribute} or unreadable_process.
    """
    try:
        model = parse_bpmn(xml)
    except ElementTree.ParseError as e:
        line, column = e.position
        raise StudioError("unreadable_xml", f"Not a readable BPMN document: the XML has a {e}.", line=line, column=column) from e
    except KeyError as e:
        attribute = e.args[0]
        raise StudioError("unreadable_attribute", f"Not a readable BPMN document: an element has no {attribute} attribute.", attribute=attribute) from e
    except ValueError as e:  # parse_bpmn's one ValueError: not exactly one process
        raise StudioError("unreadable_process", f"Not a readable BPMN document: {str(e).removeprefix('BPMN: ')}.") from e
    return [
        {"rule": v.rule, "severity": v.severity, "element_id": v.element_id, "message": v.message}
        for v in lint_model(model)
    ]


def params_from_toml(text: str) -> dict:
    """A parameter file's text as the dict the studio takes (its TOML tables).

    Text that isn't TOML raises StudioError "unreadable_toml" with the line and
    column of the problem ("at end of document" counts as after the last character).
    """
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        found = _TOML_AT.search(str(e))
        if found:
            line, column = int(found[1]), int(found[2])
        else:
            lines = text.split("\n")
            line, column = len(lines), len(lines[-1]) + 1
        raise StudioError("unreadable_toml", f"Not a readable parameter file: {e}", line=line, column=column) from e
