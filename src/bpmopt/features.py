"""Case-level feature table for the ML tasks (tickets 11 and 12).

One row per case with what is known the moment it starts: its start time and
the attributes drawn at arrival. Nothing that happens later (durations,
branches taken, the end time) goes in, so a model can't learn from the future.
Targets such as cycle time or rework are computed separately and joined on
case_id.
"""

import pandas as pd

from bpmopt.event_log import LOG_COLUMNS


def attribute_names(log: pd.DataFrame) -> list[str]:
    """Case attribute columns of a log, in log order: everything after the fixed columns."""
    return [column for column in log.columns if column not in LOG_COLUMNS]


def case_features(log: pd.DataFrame) -> pd.DataFrame:
    """One row per case, indexed by case_id: start_time, then the case attributes.

    start_time is the earliest ready time of the case (same as cycle_times uses).
    It orders the chronological split; it isn't meant as a model input.
    """
    by_case = log.groupby("case_id", sort=True)
    features = by_case[attribute_names(log)].first()
    features.insert(0, "start_time", by_case.ready_time.min())
    return features


def chronological_split(table: pd.DataFrame, train_share: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    """First train_share of the cases by start time for training, the rest for testing. Never random.

    Ties in start time (e.g. all cases arriving at time 0) keep case_id order.
    """
    if not 0 < train_share < 1:
        raise ValueError(f"train_share must be between 0 and 1, got {train_share}")
    ordered = table.sort_values("start_time", kind="stable")
    n_train = round(len(ordered) * train_share)
    return ordered.iloc[:n_train], ordered.iloc[n_train:]
