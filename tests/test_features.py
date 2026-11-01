"""Case-level feature table and the chronological split."""

import pandas as pd

from bpmopt.features import case_features, chronological_split

ATTRIBUTES = ["complexity", "project_type", "integrations", "workload"]


def test_feature_table_has_one_row_per_case_with_its_start_time_and_attributes(simulate_fixture):
    log = simulate_fixture("rework_with_activity", n_cases=100, params="rework_with_activity.ml")

    features = case_features(log)

    assert list(features.columns) == ["start_time", *ATTRIBUTES]
    assert sorted(features.index) == sorted(log.case_id.unique())
    starts = log[log.element_type == "startEvent"].set_index("case_id")
    pd.testing.assert_series_equal(features.start_time, starts.start_time.loc[features.index], check_names=False)
    pd.testing.assert_frame_equal(features[ATTRIBUTES], starts[ATTRIBUTES].loc[features.index], check_names=False)


def test_features_only_use_what_is_known_when_the_case_starts(simulate_fixture):
    log = simulate_fixture("rework_with_activity", n_cases=100, params="rework_with_activity.ml")
    # Cut each case off at its start: every row that begins after the case's first moment goes.
    case_start = log.groupby("case_id").ready_time.transform("min")
    at_start = log[log.start_time <= case_start]

    pd.testing.assert_frame_equal(case_features(at_start), case_features(log))


def test_split_puts_the_earliest_cases_in_training_whatever_the_row_order(simulate_fixture):
    log = simulate_fixture("rework_with_activity", n_cases=100, params="rework_with_activity.ml")
    shuffled = case_features(log).sample(frac=1, random_state=0)

    train, test = chronological_split(shuffled, train_share=0.8)

    assert (len(train), len(test)) == (80, 20)
    assert train.start_time.max() <= test.start_time.min()
    assert set(train.index) | set(test.index) == set(shuffled.index)
