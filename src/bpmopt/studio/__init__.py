"""The studio's Python seam: what the studio page calls in the browser (Pyodide).

Everything here is JSON in, JSON out: BPMN as an XML string, parameters as the
parameter file's tables in a dict (see bpmopt.parameters), results as dicts
of floats and lists. No file paths, so the page never needs a file system.
The worker calls these functions by name (web/studio/worker.mjs); the
modules behind them are:

- runs: simulate_summary, compare
- defaults: default_parameters, set_parameter, fixed_branches
- suggestions: apply_suggestion, suggestions (on the as-is preset)
- diff: diff_designs
- reading: lint_xml, params_from_toml; toml_writer: params_to_toml
- errors: StudioError, the refusals the page puts in words by code

Simulation goes through the same simulate + replication seeds as the scenario
runner, so the studio and the notebook give the same numbers for the same
model, parameters, cases, replications and seed.

Only the simulation path may be imported from here: no ml, features, results
or planted, which pull in scikit-learn and SHAP or aren't needed in the browser.
"""

from bpmopt.studio.defaults import (
    DEFAULT_CAPACITY,
    DEFAULT_DURATION,
    RESET_CASES,
    RESET_SEED,
    STUDIO_DEFAULT,
    STUDIO_EDIT,
    default_parameters,
    fixed_branches,
    set_parameter,
)
from bpmopt.studio.diff import diff_designs
from bpmopt.studio.errors import ERROR_CODES, StudioError
from bpmopt.studio.reading import lint_xml, params_from_toml
from bpmopt.studio.runs import PAIRED_ON, compare, simulate_summary
from bpmopt.studio.suggestions import apply_suggestion, suggestions
from bpmopt.studio.toml_writer import EXPORT_HEADER, params_to_toml

__all__ = [
    "DEFAULT_CAPACITY",
    "DEFAULT_DURATION",
    "ERROR_CODES",
    "EXPORT_HEADER",
    "PAIRED_ON",
    "RESET_CASES",
    "RESET_SEED",
    "STUDIO_DEFAULT",
    "STUDIO_EDIT",
    "StudioError",
    "apply_suggestion",
    "compare",
    "default_parameters",
    "diff_designs",
    "fixed_branches",
    "lint_xml",
    "params_from_toml",
    "params_to_toml",
    "set_parameter",
    "simulate_summary",
    "suggestions",
]
