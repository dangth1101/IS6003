"""Export the simulated event log as CSV, the format of the book's Fig. 11.4 (§11.3, p.423).

The book's log has one row per event with CaseID, EventID, Timestamp, Activity
and Resource. Ours keeps the same layout with these columns:

- CaseID -> case_id, EventID -> event_id ("<case>-<n>", the n-th event of the case)
- Activity -> activity_label (plus activity_id and element_type)
- Resource -> lane_label (plus lane_id). A lane is a resource pool, not a person
- Timestamp -> ready_time, start_time and end_time. Fig. 11.4 has one timestamp
  per event; §11.5 (pp.443-444) needs start and end to split waiting time from
  processing time, so we keep all three
- case attributes last, as the domain-specific data the book mentions on p.422

Times are working days since the simulation started, rounded to 4 decimals.
"""

from pathlib import Path

import pandas as pd

# The fixed columns of a simulated log, in order. Case attributes follow them.
LOG_COLUMNS = [
    "case_id",
    "activity_id",
    "activity_label",
    "element_type",
    "lane_id",
    "lane_label",
    "ready_time",
    "start_time",
    "end_time",
    "flow_id",
]


def export_csv(log: pd.DataFrame, path: str | Path) -> Path:
    """Write the log to path as CSV, with an event ID per row. Returns the path."""
    path = Path(path)
    events = log.copy()
    n = events.groupby("case_id").cumcount() + 1
    events.insert(1, "event_id", events.case_id.astype(str) + "-" + n.astype(str))
    times = ["ready_time", "start_time", "end_time"]
    events[times] = events[times].round(4)  # 1e-4 working days is a few seconds
    events.to_csv(path, index=False)
    return path
