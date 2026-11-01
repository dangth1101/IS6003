import pytest

from bpmopt.analysis import mean_cycle_time


def test_mean_cycle_time_of_a_sequence_matches_the_book_formula(simulate_fixture):
    # Book §7.1.1, sequence: CT = T1 + T2 + T3 = 2.0 + 5.5 + 3.0 working days.
    log = simulate_fixture("sequence", n_cases=100)

    assert mean_cycle_time(log) == pytest.approx(10.5, abs=1e-9)
