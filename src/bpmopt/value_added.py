"""Load the value-added classification of a model's tasks (book §6.1, pp.213-218).

The classification is human judgment, so it lives in a TOML file next to the
model, keyed by task ID, and goes into the `value_added` section of the results:

    [Task_BuildApplication]
    class = "VA"                    # VA, BVA or NVA
    reason = "One line on why."
"""

import tomllib
from pathlib import Path

import pandas as pd

from bpmopt.bpmn import ProcessModel

CLASSES = ("VA", "BVA", "NVA")


def load_value_added(path: str | Path, model: ProcessModel) -> dict[str, dict[str, str]]:
    """Task ID -> {"class", "reason"}. Raises ValueError unless every task of the model has exactly one entry."""
    path = Path(path)
    with path.open("rb") as f:
        entries = tomllib.load(f)  # TOML itself rejects a task ID listed twice

    tasks = {n.id for n in model.nodes_of_type("task")}
    missing = sorted(tasks - set(entries))
    if missing:
        raise ValueError(f"{path}: no classification for {', '.join(missing)}")
    unknown = sorted(set(entries) - tasks)
    if unknown:
        raise ValueError(f"{path}: not tasks of the model: {', '.join(unknown)}")

    value_added = {}
    for task_id, entry in entries.items():
        if entry.get("class") not in CLASSES:
            raise ValueError(f"{path}: {task_id}: class must be one of {', '.join(CLASSES)}")
        if not str(entry.get("reason", "")).strip():
            raise ValueError(f"{path}: {task_id}: reason is missing")
        value_added[task_id] = {"class": entry["class"], "reason": entry["reason"]}
    return value_added


def time_per_class(log: pd.DataFrame, value_added: dict[str, dict[str, str]]) -> pd.DataFrame:
    """Per class (VA, BVA, NVA): number of tasks, task time per case in working days, and share of all task time.

    Task time is start to end of each task run, so a task that reruns in a
    rework loop counts every run. Waiting isn't task time and isn't counted.
    """
    classes = pd.Series({task_id: entry["class"] for task_id, entry in value_added.items()})
    runs = log[log.element_type == "task"]
    days = (runs.end_time - runs.start_time).groupby(runs.activity_id.map(classes)).sum() / log.case_id.nunique()
    table = pd.DataFrame(
        {"tasks": classes.value_counts(), "days_per_case": days},
        index=pd.Index(CLASSES, name="class"),
    ).fillna(0)
    table["tasks"] = table.tasks.astype(int)
    table["share"] = table.days_per_case / table.days_per_case.sum()
    return table
