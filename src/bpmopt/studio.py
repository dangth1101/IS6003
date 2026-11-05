"""The studio's Python seam: what the studio page calls in the browser (Pyodide).

Everything here is JSON in, JSON out: BPMN as an XML string, parameters as the
parameter file's tables in a dict (see bpmopt.parameters), results as dicts
of floats and lists. No file paths, so the page never needs a file system.

Simulation goes through the same simulate + replication seeds as the scenario
runner, so the studio and the notebook give the same numbers for the same
model, parameters, cases, replications and seed.

Only the simulation path may be imported from here: no ml, features, results
or planted, which pull in scikit-learn and SHAP or aren't needed in the browser.
"""

from collections.abc import Callable

import numpy as np

from bpmopt.analysis import cycle_times
from bpmopt.bpmn import parse_bpmn
from bpmopt.parameters import parse_parameters
from bpmopt.scenarios import estimate, replication_seeds
from bpmopt.simulation import simulate


def simulate_summary(
    xml: str,
    params: dict,
    n_cases: int,
    seed: int,
    replications: int,
    progress: Callable[[int, int], None] | None = None,
) -> dict:
    """Simulate the model `replications` times and summarise its cycle time.

    Replication r runs with replication_seeds(seed, replications)[r], like the
    scenario runner. Returns the run settings, the mean cycle time over
    replications with its 95% CI (`cycle_time.mean`, shaped like a scenario's),
    and each replication's mean (`replication_means`, kept to pair two runs).
    progress, if given, is called with (replications done, replications) after each one.
    """
    if replications < 2:
        raise ValueError(f"need at least 2 replications for a confidence interval, got {replications}")
    model = parse_bpmn(xml)
    parameters = parse_parameters(params, model)
    means = []
    for r, replication_seed in enumerate(replication_seeds(seed, replications)):
        log = simulate(model, parameters, n_cases=n_cases, seed=replication_seed)
        means.append(float(cycle_times(log, parameters.cycle_time_end).mean()))
        if progress is not None:
            progress(r + 1, replications)
    return {
        "n_cases": n_cases,
        "seed": seed,
        "replications": replications,
        "cycle_time": {"mean": estimate(np.array(means))},
        "replication_means": means,
    }
