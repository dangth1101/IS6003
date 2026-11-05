"""The studio seam: bpmopt.studio and the string / dict readers it builds on.

The studio page runs these in the browser (Pyodide), so inputs are BPMN XML
strings and parameter dicts, never file paths, and outputs are JSON-shaped.
"""

import json
import re
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

from bpmopt.bpmn import parse_bpmn, read_bpmn
from bpmopt.parameters import load_parameters, parse_parameters
from bpmopt.scenarios import Catalog, run_scenarios
from bpmopt.studio import simulate_summary

ROOT = Path(__file__).parents[1]
AS_IS = ROOT / "models" / "as_is.bpmn"
AS_IS_PARAMS = ROOT / "models" / "as_is.params.toml"


def as_is_preset() -> tuple[str, dict]:
    """The as-is preset as the page sends it: the BPMN text and the parameter file as a dict."""
    return AS_IS.read_text(), tomllib.loads(AS_IS_PARAMS.read_text())


def test_a_bpmn_string_reads_to_the_same_model_as_its_file():
    assert parse_bpmn(AS_IS.read_text()) == read_bpmn(AS_IS)


def test_a_parameter_dict_loads_to_the_same_parameters_as_its_file():
    raw = tomllib.loads(AS_IS_PARAMS.read_text())

    assert parse_parameters(raw) == load_parameters(AS_IS_PARAMS)


def test_simulate_summary_gives_the_scenario_runners_as_is_numbers():
    # The notebook's path: the empty scenario of a catalog, with the same seed, cases and replications.
    as_is_only = Catalog("test", (), {frozenset(): (read_bpmn(AS_IS), load_parameters(AS_IS_PARAMS))})
    (expected,) = run_scenarios(as_is_only, n_cases=100, seed=7, replications=3)

    summary = simulate_summary(*as_is_preset(), n_cases=100, seed=7, replications=3)

    assert summary["replication_means"] == expected["replication_means"]
    assert summary["cycle_time"]["mean"] == expected["cycle_time"]["mean"]


def test_simulate_summary_of_the_as_is_preset_matches_the_parity_fixture():
    # The studio's default run. The browser check compares against the same file.
    parity = json.loads((ROOT / "tests" / "fixtures" / "studio_parity.json").read_text())

    summary = simulate_summary(*as_is_preset(), n_cases=parity["n_cases"], seed=parity["seed"], replications=parity["replications"])

    assert summary["replication_means"] == parity["replication_means"]
    assert summary["cycle_time"] == parity["cycle_time"]


def test_simulate_summary_reports_progress_after_each_replication():
    calls = []

    simulate_summary(*as_is_preset(), n_cases=20, seed=1, replications=3, progress=lambda done, total: calls.append((done, total)))

    assert calls == [(1, 3), (2, 3), (3, 3)]


def test_simulate_summary_is_json_serialisable():
    summary = simulate_summary(*as_is_preset(), n_cases=20, seed=1, replications=2)

    assert json.loads(json.dumps(summary)) == summary


def test_the_studio_imports_nothing_outside_the_simulation_path():
    # In the browser there is no scikit-learn or SHAP; a fresh interpreter shows what importing the studio pulls in.
    banned = ["bpmopt.ml", "bpmopt.features", "bpmopt.results", "bpmopt.planted", "sklearn", "shap"]
    code = f"import sys, bpmopt.studio; print([m for m in {banned!r} if m in sys.modules])"

    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout

    assert out.strip() == "[]"


STUDIO = ROOT / "web" / "studio"
REBUILD = "rebuild with: uv run python scripts/build_studio.py"


def _source_files() -> dict[str, bytes]:
    """What the wheel must hold: every file of src/bpmopt/ that hatchling packs (it skips git-ignored files)."""
    src = ROOT / "src"
    return {
        path.relative_to(src).as_posix(): path.read_bytes()
        for path in sorted((src / "bpmopt").rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts and path.name != ".DS_Store"
    }


def test_the_committed_wheel_holds_the_current_package_source():
    # The browser installs this wheel, so a stale one would run old code there.
    (wheel,) = STUDIO.glob("bpmopt-*-py3-none-any.whl")
    with zipfile.ZipFile(wheel) as zf:
        packed = {name: zf.read(name) for name in zf.namelist() if name.startswith("bpmopt/")}

    source = _source_files()

    assert sorted(packed) == sorted(source), REBUILD
    stale = [name for name in source if packed[name] != source[name]]
    assert stale == [], f"stale in the wheel: {stale}; {REBUILD}"
    # micropip needs the real wheel file name, and the worker names it.
    assert wheel.name in (STUDIO / "worker.mjs").read_text(encoding="utf-8")


def test_the_studio_presets_are_the_models_as_is_files():
    for name in ["as_is.bpmn", "as_is.params.toml"]:
        assert (STUDIO / "presets" / name).read_bytes() == (ROOT / "models" / name).read_bytes(), f"{name}: {REBUILD}"


def test_the_studio_text_is_the_content_file():
    content = tomllib.loads((ROOT / "src" / "bpmopt" / "content" / "studio.en.toml").read_text(encoding="utf-8"))

    assert json.loads((STUDIO / "studio.en.json").read_text(encoding="utf-8")) == content, REBUILD


def test_the_studio_uses_exactly_the_labels_of_its_content_file():
    # All studio wording comes from the content file: t("key") in the page, and the
    # loading stages the worker reports, which the page shows as labels.
    page = (STUDIO / "index.html").read_text(encoding="utf-8")
    worker = (STUDIO / "worker.mjs").read_text(encoding="utf-8")
    used = set(re.findall(r"""\bt\(["'](\w+)["']""", page)) | set(re.findall(r"""\bloading\(["'](\w+)["']""", worker))
    content = tomllib.loads((ROOT / "src" / "bpmopt" / "content" / "studio.en.toml").read_text(encoding="utf-8"))

    assert used == set(content["labels"])


def test_the_report_page_and_the_studio_link_to_each_other():
    report = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    studio = (STUDIO / "index.html").read_text(encoding="utf-8")

    assert re.search(r"""href:?=?\s*["']studio/["']""", report)
    assert re.search(r"""href=["']\.\./["']""", studio)
