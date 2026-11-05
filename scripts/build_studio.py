"""Build what the studio page (web/studio/) loads from the repo.

    uv run python scripts/build_studio.py

- the bpmopt wheel, built from src/ with uv (hatchling, reproducible: an
  unchanged source gives the same bytes), which Pyodide installs;
- the as-is preset and the change catalog with its models, copied from models/;
- the studio text, src/bpmopt/content/studio.en.toml as JSON.

Rerun it after changing anything under src/bpmopt/ or the preset models, and
commit web/studio/. tests/test_studio.py fails while any of them is stale.
"""

import json
import shutil
import subprocess
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDIO = ROOT / "web" / "studio"
# The as-is preset and the change catalog with its models, which apply_suggestion needs.
PRESETS = ["as_is.bpmn", "as_is.params.toml", "to_be.catalog.toml", "to_be_c1.bpmn", "to_be_c2.bpmn", "to_be.bpmn"]


def build_wheel() -> Path:
    with tempfile.TemporaryDirectory() as out:
        subprocess.run(["uv", "build", "--wheel", "--out-dir", out, str(ROOT)], check=True)
        (wheel,) = Path(out).glob("bpmopt-*-py3-none-any.whl")
        for old in STUDIO.glob("bpmopt-*.whl"):
            old.unlink()
        return Path(shutil.copy2(wheel, STUDIO / wheel.name))


def copy_presets() -> None:
    (STUDIO / "presets").mkdir(exist_ok=True)
    for name in PRESETS:
        shutil.copyfile(ROOT / "models" / name, STUDIO / "presets" / name)


def write_text() -> None:
    for source in sorted((ROOT / "src" / "bpmopt" / "content").glob("studio.*.toml")):
        content = tomllib.loads(source.read_text(encoding="utf-8"))
        target = STUDIO / source.with_suffix(".json").name
        target.write_text(json.dumps(content, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    STUDIO.mkdir(parents=True, exist_ok=True)
    print(f"wheel: {build_wheel().relative_to(ROOT)}")
    copy_presets()
    write_text()
    print("presets and text written to web/studio/")
