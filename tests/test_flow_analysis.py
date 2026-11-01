"""Flow analysis (book §7.1.1) against the book's worked examples.

Expected values are the book's own numbers, with the page they come from.
The one exception is the rework block with a task on its loop-back arc, which
the book doesn't cover; that expected value is our own derivation.

The book has two known slips near these examples: Solution 7.4 (p.289) names
the wrong task as having slack, and Example 7.5 (p.269) swaps two processing
times in its text. They concern the critical path and unit load, not cycle
time, so no test here relies on them.
"""

import pytest

from bpmopt.bpmn import read_bpmn
from bpmopt.flow_analysis import theoretical_cycle_time
from bpmopt.parameters import load_parameters


@pytest.fixture
def flow_analysis(fixtures_dir):
    def run(model: str, params: str | None = None) -> float:
        return theoretical_cycle_time(
            read_bpmn(fixtures_dir / f"{model}.bpmn"),
            load_parameters(fixtures_dir / f"{params or model}.params.toml"),
        )

    return run


def test_sequence_is_the_sum_of_its_tasks(flow_analysis):
    # Fig. 7.1, p.256: "20 + 10 = 30 h".
    assert flow_analysis("book_fig7_1") == pytest.approx(30.0)


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        # p.257: 50/50 gives 25 h; 90/10 gives 10 + (0.9 x 20 + 0.1 x 10) = 29 h.
        ("book_fig7_2.even", 25.0),
        ("book_fig7_2", 29.0),
    ],
)
def test_xor_block_weights_its_branches_by_probability(flow_analysis, params, expected):
    assert flow_analysis("book_fig7_2", params) == pytest.approx(expected)


def test_an_empty_xor_branch_counts_as_zero(flow_analysis):
    # Fig. 7.9, p.260: 10 + 20 + (0.2 x 20 + 0.8 x 0) = 34.
    assert flow_analysis("book_fig7_9") == pytest.approx(34.0)


def test_and_block_takes_as_long_as_its_slowest_branch(flow_analysis):
    # Fig. 7.4, p.258: "10 + 20 = 30 h".
    assert flow_analysis("book_fig7_4") == pytest.approx(30.0)


def test_rework_block_divides_its_body_by_one_minus_r(flow_analysis):
    # Fig. 7.7, p.260: 10 + 20 / (1 - 0.2) = 10 + 25 = 35.
    assert flow_analysis("book_fig7_7") == pytest.approx(35.0)


def test_rework_body_can_hold_several_tasks(flow_analysis):
    # Solution 7.2, p.288 (Fig. 3.13): 2 + 8 + (4 + 4) / (1 - 0.2) = 20 days.
    assert flow_analysis("book_fig3_13") == pytest.approx(20.0)


def test_a_task_on_the_loop_back_arc_runs_r_over_one_minus_r_times(flow_analysis):
    # Not in the book: every book example has an empty loop-back arc. Our derivation from the
    # same geometric series (p.259): the body runs 1/(1 - r) times and the loop-back task
    # r/(1 - r) times, so CT = (T + r x R) / (1 - r) = (4 + 0.25 x 2) / 0.75 = 6.
    assert flow_analysis("rework_with_activity") == pytest.approx(6.0)


@pytest.mark.parametrize(
    ("model", "params", "expected"),
    [
        # Example 7.1, p.259 (Fig. 7.6): 1 + 3 + 3 + (0.6 x 1 + 0.4 x 2) = 8.4 days.
        ("book_fig7_6", None, 8.4),
        # Example 7.2, p.261 (Fig. 7.10): 1 / (1 - 0.2) + 3 + 3 + 1.4 = 8.65 days.
        ("book_fig7_10", None, 8.65),
        # Example 7.3, p.262: the same formulas on processing times give the theoretical
        # cycle time, 2 / (1 - 0.2) + 3 + 2 + 0.6 x 2 + 0.4 x 0.5 = 8.9 h.
        ("book_fig7_10", "book_fig7_10.processing", 8.9),
    ],
)
def test_credit_application_examples_nest_all_four_blocks(flow_analysis, model, params, expected):
    assert flow_analysis(model, params) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        # A rework split with a third branch to its own end event, the corrected as-is model's
        # approval step. Worked by hand in the params file: 2 + 0.8 x 8 = 8.4.
        ("proposal_rejected", 8.4),
        # An early exit inside an XOR-block, whose other branch runs on to the outer join:
        # 0.5 x 0.8 x 2 + 0.5 x 4 + 0.9 x 10 = 11.8.
        ("early_exit_in_block", 11.8),
    ],
)
def test_a_branch_that_ends_at_its_own_end_event_weights_the_rest_of_the_process(flow_analysis, model, expected):
    # Not in the book: its blocks all end in a join. Our derivation, with the same weighting
    # as the XOR formula (7.2): a case that has ended spends no more time, so everything after
    # an early exit counts with the probability of not having ended.
    assert flow_analysis(model) == pytest.approx(expected)


# rework_with_activity.logistic: P(fail) = logistic(-2 + complexity + 1.5 x [mobile]).
# Attribute weights from the params file, P(fail) worked by hand per group.
LOGISTIC_GROUPS = [
    # (weight, P(fail))
    (0.4 * 0.7, 0.268941),  # complexity 1, web: logistic(-1)
    (0.4 * 0.7, 0.5),  # complexity 2, web: logistic(0)
    (0.2 * 0.7, 0.731059),  # complexity 3, web: logistic(1)
    (0.4 * 0.3, 0.622459),  # complexity 1, mobile: logistic(0.5)
    (0.4 * 0.3, 0.817574),  # complexity 2, mobile: logistic(1.5)
    (0.2 * 0.3, 0.924142),  # complexity 3, mobile: logistic(2.5)
]


def test_logistic_splits_average_the_formula_over_cases_not_the_probability(flow_analysis):
    # Not in the book, which only has fixed probabilities. Once a case's attributes are known
    # its probabilities are fixed, so the book's formula holds per case: (4 + r x 2) / (1 - r),
    # with T = 4 and R = 2 from rework_with_activity. The process CT is its mean over cases.
    # Putting the mean r into the formula instead would come out far lower, since 1 / (1 - r)
    # is convex.
    exact = sum(w * (4 + r * 2) / (1 - r) for w, r in LOGISTIC_GROUPS)
    mean_r = sum(w * r for w, r in LOGISTIC_GROUPS)
    plugged_in = (4 + mean_r * 2) / (1 - mean_r)

    ct = flow_analysis("rework_with_activity", "rework_with_activity.logistic")

    assert ct == pytest.approx(exact, rel=0.02)  # sampled attributes, so not exact
    assert ct > 1.3 * plugged_in


def test_a_logistic_split_without_attribute_effects_gives_the_plain_formula(fixtures_dir, tmp_path):
    # logistic(0 + 0 x complexity) = 0.5 for every case, so the average over cases must equal
    # the book's formula with r = 0.5: (4 + 0.5 x 2) / 0.5 = 10, with no sampling error.
    params = (fixtures_dir / "rework_with_activity.logistic.params.toml").read_text()
    params = params.replace("intercept = -2.0, complexity = 1.0, project_type = { mobile = 1.5 }", "intercept = 0.0, complexity = 0.0")
    path = tmp_path / "flat.params.toml"
    path.write_text(params)

    ct = theoretical_cycle_time(read_bpmn(fixtures_dir / "rework_with_activity.bpmn"), load_parameters(path))

    assert ct == pytest.approx(10.0, abs=1e-9)
