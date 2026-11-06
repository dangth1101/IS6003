"""Write web/demo/replay.json, the simulation run the flow demo page animates.

One run of the as-is and the full to-be (C1-C4), seed 42 like the report, cut to
the 1.5 simulated years right after the warm-up (working days 250 to 625). In
that window the as-is QC queue fills from empty to about 8 waiting checks on
average, while the to-be one stays under 1.

    uv run python scripts/build_demo_data.py
"""

from pathlib import Path

from bpmopt.bpmn import read_bpmn
from bpmopt.parameters import load_parameters
from bpmopt.replay import build_replay, write_replay
from bpmopt.scenarios import load_catalog

ROOT = Path(__file__).resolve().parents[1]
SEED = 42
LENGTH = 375  # working days, 1.5 simulated years


def main() -> None:
    model = read_bpmn(ROOT / "models" / "as_is.bpmn")
    params = load_parameters(ROOT / "models" / "as_is.params.toml", model)
    catalog = load_catalog(ROOT / "models" / "to_be.catalog.toml", model=model, params=params)
    replay = build_replay(catalog, seed=SEED, start=params.warm_up, length=LENGTH)
    path = write_replay(replay, ROOT / "web" / "demo" / "replay.json")
    print(f"wrote {path.relative_to(ROOT)} ({path.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
