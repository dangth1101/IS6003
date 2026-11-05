"""The studio's refusals: a stable code and its data, for the page to put in words.

The page renders a refusal from the [errors] table of the studio content file
(src/bpmopt/content/studio.<lang>.toml), filling the template's {placeholders}
from data, so a translation never touches Python. The message is for a
notebook or pytest only; the page doesn't show it.
"""

# Every code a studio function raises. The content file has a text for each (a test checks).
ERROR_CODES = (
    # lint_xml and params_from_toml: a document that can't be read
    "unreadable_xml",  # {line, column}
    "unreadable_attribute",  # {attribute}
    "unreadable_process",
    "unreadable_toml",  # {line, column}
    # apply_suggestion
    "hand_edited",
    "unknown_changes",  # {changes, catalog}
    # compare
    "not_comparable",  # {settings: [{setting, baseline, variant}]}
    # set_parameter: {entry}, plus task for not_a_task
    "not_settable",
    "unknown_element",
    "not_a_task",
    "duration_order",
    "duration_negative",
    "branch_shares",
    "capacity_whole",
    "rate_positive",
    "warm_up_negative",
    "invalid_value",  # any other rule of the parameter file
)


class StudioError(ValueError):
    """A refusal: ValueError(message) with code (one of ERROR_CODES) and data (JSON-serialisable)."""

    def __init__(self, code: str, message: str, **data):
        if code not in ERROR_CODES:
            raise ValueError(f"unknown studio error code {code!r}")
        super().__init__(message)
        self.code = code
        self.data = data
