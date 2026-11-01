import pandas as pd


def test_same_seed_gives_identical_log(simulate_fixture):
    first = simulate_fixture("sequence", seed=7)
    second = simulate_fixture("sequence", seed=7)

    assert len(first) > 0
    pd.testing.assert_frame_equal(first, second)


def test_every_case_has_one_start_and_reaches_the_end_event(simulate_fixture):
    log = simulate_fixture("sequence", n_cases=20)

    for case_id, trace in log.groupby("case_id"):
        starts = trace[trace.element_type == "startEvent"]
        ends = trace[trace.element_type == "endEvent"]
        assert list(starts.activity_id) == ["Start_RequestReceived"], case_id
        assert list(ends.activity_id) == ["End_AppReleased"], case_id
        assert trace.iloc[0].element_type == "startEvent"
        assert trace.iloc[-1].element_type == "endEvent"
    assert log.case_id.nunique() == 20


def test_log_has_the_event_log_columns(simulate_fixture):
    log = simulate_fixture("sequence", n_cases=1)

    for column in ["case_id", "activity_id", "activity_label", "lane_id", "lane_label", "ready_time", "start_time", "end_time"]:
        assert column in log.columns
    tasks = log[log.element_type == "task"]
    assert list(tasks.activity_label) == ["Write specification", "Build application", "Test application"]
    assert set(log.lane_id) == {"Lane_Dev"}
    assert set(log.lane_label) == {"Development team"}
