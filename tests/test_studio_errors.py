"""What the page shows when the studio refuses something.

A refusal is a StudioError: a ValueError whose message reads well in a
notebook or in pytest, plus a stable code and its data. The page never shows
the message; it renders the code's text from the [errors] table of the studio
content file with the data filled in, so a translation is a content edit.
"""

import re
import tomllib
from pathlib import Path

import pytest

from bpmopt.studio import (
    ERROR_CODES,
    StudioError,
    apply_suggestion,
    compare,
    lint_xml,
    params_from_toml,
    set_parameter,
    simulate_summary,
)

ROOT = Path(__file__).parents[1]
MODELS = ROOT / "models"
STUDIO = ROOT / "web" / "studio"
CONTENT = tomllib.loads((ROOT / "src" / "bpmopt" / "content" / "studio.en.toml").read_text(encoding="utf-8"))
PRESET_FILES = ["as_is.bpmn", "as_is.params.toml", "to_be.catalog.toml", "to_be_c1.bpmn", "to_be_c2.bpmn", "to_be.bpmn"]
FLOW_WITHOUT_ENDS = (
    '<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL"><process id="P">'
    '<sequenceFlow id="Flow_Half"/></process></definitions>'
)
TWO_PROCESSES = (
    '<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL"><process id="P1"/><process id="P2"/></definitions>'
)


def as_is() -> tuple[str, dict]:
    return (MODELS / "as_is.bpmn").read_text(), tomllib.loads((MODELS / "as_is.params.toml").read_text())


def preset() -> dict[str, str]:
    return {name: (MODELS / name).read_text() for name in PRESET_FILES}


def hand_edited() -> str:
    return as_is()[0].replace('name="Run functional tests"', 'name="Run all functional tests"')


def set_entry(entry: str, fields: dict):
    return lambda: set_parameter(*as_is(), entry, fields)


def not_comparable():
    run = {"n_cases": 20, "seed": 7, "replications": 2}
    baseline = simulate_summary(*as_is(), **run)
    variant = simulate_summary(*as_is(), **(run | {"seed": 8, "n_cases": 30}))
    return compare(baseline, variant)


REFUSALS = {
    "unreadable_xml": (lambda: lint_xml("not xml"), {"line": 1, "column": 0}),
    "unreadable_attribute": (lambda: lint_xml(FLOW_WITHOUT_ENDS), {"attribute": "sourceRef"}),
    "unreadable_process": (lambda: lint_xml(TWO_PROCESSES), {}),
    "unreadable_toml": (lambda: params_from_toml('version = "x"\nrate ='), {"line": 2}),
    "hand_edited": (lambda: apply_suggestion(hand_edited(), ["C4"], preset()), {}),
    "unknown_changes": (lambda: apply_suggestion(as_is()[0], ["C1", "C9"], preset()), {"changes": ["C9"]}),
    "not_comparable": (not_comparable, {
        "settings": [{"setting": "seed", "baseline": 7, "variant": 8}, {"setting": "n_cases", "baseline": 20, "variant": 30}],
    }),
    "not_settable": (set_entry("attributes.complexity", {"distribution": {"poisson": 1}}), {"entry": "attributes.complexity"}),
    "unknown_element": (set_entry("tasks.Task_Nowhere", {"duration": {"fixed": 1}}), {"entry": "tasks.Task_Nowhere"}),
    "not_a_task": (set_entry("cycle_time", {"ends_at": "Gateway_ProposalSplit"}), {"task": "Gateway_ProposalSplit"}),
    "duration_order": (set_entry("tasks.Task_DraftPlan", {"duration": {"triangular": [5, 3, 9]}}), {"entry": "tasks.Task_DraftPlan"}),
    "duration_negative": (set_entry("tasks.Task_DraftPlan", {"duration": {"triangular": [-1, 3, 9]}}), {"entry": "tasks.Task_DraftPlan"}),
    "branch_shares": (
        set_entry("gateways.Gateway_ProposalSplit",
                  {"branches": {"Flow_ProposalApproved": 0.5, "Flow_ProposalChangesRequested": 0.2, "Flow_ProposalRejected": 0.2}}),
        {"entry": "gateways.Gateway_ProposalSplit"},
    ),
    "capacity_whole": (set_entry("lanes.Lane_QualityControl", {"capacity": 0}), {"entry": "lanes.Lane_QualityControl"}),
    "rate_positive": (set_entry("arrivals", {"rate": -1}), {"entry": "arrivals"}),
    "warm_up_negative": (set_entry("warm_up", {"length": -5}), {"entry": "warm_up"}),
    "invalid_value": (set_entry("tasks.Task_DraftPlan", {"duration": {"triangular": [1, 2]}}), {"entry": "tasks.Task_DraftPlan"}),
}


def refusal(call) -> StudioError:
    with pytest.raises(StudioError) as caught:
        call()
    return caught.value


def placeholders(template: str) -> set[str]:
    return set(re.findall(r"\{(\w+)\}", template))


@pytest.mark.parametrize("code", REFUSALS)
def test_a_refusal_has_a_stable_code_and_the_data_its_text_needs(code):
    call, data = REFUSALS[code]

    error = refusal(call)

    assert error.code == code
    assert {key: error.data.get(key) for key in data} == data
    assert placeholders(CONTENT["errors"][code]) <= set(error.data)


def test_every_code_the_studio_can_refuse_with_is_tried_above():
    assert set(REFUSALS) == set(ERROR_CODES)


def test_the_studio_text_has_text_for_every_error_code_of_python_and_the_page():
    # The page's own codes (a file it can't fetch, a failure it didn't expect) come from studioError("...") in its modules.
    page = "\n".join(p.read_text(encoding="utf-8") for p in [STUDIO / "index.html", *sorted(STUDIO.glob("*.mjs"))])
    page_codes = set(re.findall(r"""\bstudioError\(["'](\w+)["']""", page))

    assert page_codes, "expected the page to raise some errors of its own"
    assert set(CONTENT["errors"]) == set(ERROR_CODES) | page_codes


def test_a_refusal_is_still_a_value_error_that_reads_well_in_a_notebook():
    error = refusal(lambda: apply_suggestion(hand_edited(), ["C4"], preset()))

    assert isinstance(error, ValueError)
    assert "edited by hand" in str(error)


def test_the_page_shows_no_python_message_verbatim():
    # Errors reach the page as {code, data} from the worker, never as a Python message or traceback line.
    worker = (STUDIO / "worker.mjs").read_text(encoding="utf-8")
    page = "\n".join(p.read_text(encoding="utf-8") for p in [STUDIO / "index.html", *sorted(STUDIO.glob("*.mjs"))])

    assert "StudioError" in worker
    assert "HTTP ${" not in page
    assert "e.message" not in page
