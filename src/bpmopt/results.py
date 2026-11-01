"""Assemble, validate and export the results file the static page reads.

The JSON schema in schema/results.schema.json is the contract between the
notebook and the page. Every export is validated against it.
"""

import json
import shutil
from datetime import UTC, datetime
from functools import cache
from importlib import resources
from pathlib import Path

import jsonschema
import pandas as pd

from bpmopt.analysis import mean_cycle_time
from bpmopt.parameters import Parameters

SCHEMA_VERSION = 1


def build_results(*, log: pd.DataFrame, params: Parameters, seed: int) -> dict:
    """Results without the `models` section, which export_results fills in."""
    return {
        "meta": {
            "schema_version": SCHEMA_VERSION,
            "seed": seed,
            "case_count": int(log.case_id.nunique()),
            "parameter_version": params.version,
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        },
        "baseline": {
            "time_unit": "working days",
            "cycle_time": {"mean": mean_cycle_time(log)},
        },
    }


def export_results(results: dict, out_dir: str | Path, *, models: dict[str, Path]) -> Path:
    """Copy each BPMN model into out_dir/models/ and write out_dir/results.json.

    out_dir ends up self-contained, so it can be served as a static site.
    """
    out_dir = Path(out_dir)
    (out_dir / "models").mkdir(parents=True, exist_ok=True)
    results = {**results, "models": {}}
    for key, source in models.items():
        target = Path("models") / f"{key}.bpmn"
        shutil.copyfile(source, out_dir / target)
        results["models"][key] = {"bpmn": target.as_posix()}

    validate_results(results)
    path = out_dir / "results.json"
    path.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def validate_results(results: dict) -> None:
    """Raise jsonschema.ValidationError if results break the contract."""
    jsonschema.validate(results, _schema())


@cache
def _schema() -> dict:
    return json.loads(resources.files("bpmopt").joinpath("schema/results.schema.json").read_text())
