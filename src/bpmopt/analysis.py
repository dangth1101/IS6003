"""Performance measures computed from an event log (book Ch. 7, §11.5)."""

import pandas as pd


def cycle_times(log: pd.DataFrame) -> pd.Series:
    """Cycle time per case: from the moment the case starts until it ends (book §7.1)."""
    by_case = log.groupby("case_id")
    return by_case.end_time.max() - by_case.ready_time.min()


def mean_cycle_time(log: pd.DataFrame) -> float:
    return float(cycle_times(log).mean())
