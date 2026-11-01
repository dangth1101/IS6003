from collections.abc import Callable
from pathlib import Path

import pandas as pd
import pytest

from bpmopt.bpmn import read_bpmn
from bpmopt.parameters import load_parameters
from bpmopt.simulation import simulate

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def simulate_fixture() -> Callable[..., pd.DataFrame]:
    """Simulate fixtures/<name>.bpmn with fixtures/<name>.params.toml."""

    def run(name: str, n_cases: int = 50, seed: int = 42) -> pd.DataFrame:
        model = read_bpmn(FIXTURES / f"{name}.bpmn")
        params = load_parameters(FIXTURES / f"{name}.params.toml")
        return simulate(model, params, n_cases=n_cases, seed=seed)

    return run
