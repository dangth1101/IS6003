"""CSV export of the event log, in the shape of the book's Fig. 11.4 (§11.3, p.423)."""

import pandas as pd
import pytest

from bpmopt.event_log import export_csv


@pytest.fixture
def log(simulate_fixture):
    return simulate_fixture("rework_with_activity", n_cases=30, seed=5, params="rework_with_activity.logistic")


def test_the_csv_has_the_columns_of_the_book_event_log_plus_start_and_ready_times(log, tmp_path):
    path = export_csv(log, tmp_path / "log.csv")

    csv = pd.read_csv(path)
    # Fig. 11.4: CaseID, EventID, Timestamp, Activity, Resource. One row per event.
    assert list(csv.columns[:2]) == ["case_id", "event_id"]
    assert {"activity_label", "lane_label", "ready_time", "start_time", "end_time"} <= set(csv.columns)
    assert len(csv) == len(log)
    assert csv.event_id.is_unique
    # Case attributes come last, as domain data (p.422).
    assert list(csv.columns[-2:]) == ["complexity", "project_type"]


def test_the_csv_reads_back_as_the_same_log(log, tmp_path):
    csv = pd.read_csv(export_csv(log, tmp_path / "log.csv"))

    back = csv.drop(columns="event_id")[log.columns]
    # CSV has no None vs "" (e.g. unlabeled gateways), so both read back as empty.
    # Times are rounded to 1e-4 working days, a few seconds, to keep the file readable.
    pd.testing.assert_frame_equal(back.fillna(""), log.fillna(""), check_dtype=False, atol=1e-4)


def test_times_are_written_with_four_decimals(simulate_fixture, tmp_path):
    log = simulate_fixture("sequence", n_cases=5, params="sequence.triangular")
    lines = export_csv(log, tmp_path / "log.csv").read_text().splitlines()

    header = lines[0].split(",")
    row = dict(zip(header, lines[2].split(",")))
    assert all(len(row[column].split(".")[-1]) <= 4 for column in ("ready_time", "start_time", "end_time"))


def test_event_ids_count_the_events_of_each_case_in_order(log, tmp_path):
    csv = pd.read_csv(export_csv(log, tmp_path / "log.csv"))

    first_case = csv[csv.case_id == csv.case_id.iloc[0]]
    case = first_case.case_id.iloc[0]
    assert list(first_case.event_id) == [f"{case}-{i}" for i in range(1, len(first_case) + 1)]
