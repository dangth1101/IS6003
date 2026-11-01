import pytest

from bpmopt.lint import lint


def found(violations):
    return sorted((v.rule, v.element_id) for v in violations)


def test_clean_model_has_no_violations(fixtures_dir):
    assert lint(fixtures_dir / "sequence.bpmn") == []


# Each fixture breaks exactly one rule, so the linter must report only that rule.
ONE_RULE_FIXTURES = [
    ("no_pool", [("POOL", "Process_NoPool")]),
    (
        "event_labels",
        [("EVENT-LABEL", "Start_Unlabeled"), ("EVENT-LABEL", "End_Generic"), ("EVENT-LABEL", "End_NoObject")],
    ),
    ("yes_no_arcs", [("ARC-LABEL", "Flow_Yes"), ("ARC-LABEL", "Flow_No")]),
    (
        "unreachable",
        [("REACH", "Task_ArchiveRequest"), ("REACH", "Task_NotifyRequester"), ("REACH", "End_RequesterNotified")],
    ),
    ("unsupported_element", [("SUBSET", "Timer_OneDayPassed"), ("SUBSET", "SubProcess_BuildApp")]),
    ("or_gateway", [("G5", "Gateway_OrSplit"), ("G5", "Gateway_OrJoin")]),
    ("too_many_elements", [("G7", "Process_Large")]),
    (
        "activity_labels",
        [
            ("G6", "Task_ActionNoun"),
            ("G6", "Task_Gerund"),
            ("G6", "Task_GeneralVerb"),
            ("G6", "Task_NoObject"),
            ("G6", "Task_Lowercase"),
            ("G6", "Task_Unlabeled"),
        ],
    ),
    ("duplicate_outcome", [("G3", "End_ClosedAfterRefund"), ("G3", "End_ClosedDirectly")]),
    ("single_outcome", [("G3", "End_ProposalApproved")]),
    ("many_routing_paths", [("G2", "Gateway_AndSplit"), ("G2", "Gateway_AndJoin")]),
    ("unstructured", [("G4", "Gateway_AndSplit")]),
    ("redundant_gateway", [("G1", "Gateway_PassThrough")]),
]


@pytest.mark.parametrize(("fixture", "expected"), ONE_RULE_FIXTURES, ids=[f for f, _ in ONE_RULE_FIXTURES])
def test_fixture_breaking_one_rule_reports_only_that_rule(fixtures_dir, fixture, expected):
    violations = lint(fixtures_dir / "lint" / f"{fixture}.bpmn")

    assert found(violations) == sorted(expected)
    for v in violations:
        assert "§" in v.message, v


def test_original_as_is_model_has_the_known_violations(fixtures_dir):
    violations = lint(fixtures_dir.parents[1] / "current_process.bpmn")

    as_is_tasks = [
        "request", "approve", "revise", "kick", "spec", "plan", "planapprove", "build",
        "test", "fix", "appapprove", "deploy", "operate", "monitor", "review",
    ]  # fmt: skip
    yes_no_arcs = ["Flow_4", "Flow_5", "Flow_11", "Flow_12", "Flow_15", "Flow_16", "Flow_19", "Flow_20"]
    expected = (
        [("POOL", "Process_AppDev_ASIS")]
        # "Bắt đầu" / "Kết thúc" = "Start" / "End"
        + [("EVENT-LABEL", "start"), ("EVENT-LABEL", "end")]
        # "Có" / "Không" = "Yes" / "No"
        + [("ARC-LABEL", arc) for arc in yes_no_arcs]
        # One end event, so a rejected proposal can only loop back to "revise"
        + [("G3", "end")]
        # Labels are Vietnamese, so the English verb-object heuristic flags every task
        + [("G6", task) for task in as_is_tasks]
    )
    assert found(violations) == sorted(expected)


def test_verb_object_check_is_a_warning_not_an_error(fixtures_dir):
    violations = lint(fixtures_dir / "lint" / "activity_labels.bpmn")

    assert violations
    assert {v.severity for v in violations} == {"warning"}
