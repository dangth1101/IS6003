"""Loading and validating the parameter file."""

import pytest

from bpmopt.bpmn import read_bpmn
from bpmopt.parameters import load_parameters
from bpmopt.simulation import simulate

SEQUENCE_TASKS = """
[tasks.Task_WriteSpec]
duration = { fixed = 2.0 }
rationale = "Fixture value."

[tasks.Task_BuildApp]
duration = { fixed = 5.5 }
rationale = "Fixture value."

[tasks.Task_TestApp]
duration = { triangular = [1.0, 3.0, 5.0] }
rationale = "Fixture value."
"""


@pytest.fixture
def sequence(fixtures_dir):
    return read_bpmn(fixtures_dir / "sequence.bpmn")


@pytest.fixture
def write(tmp_path):
    def write(text: str):
        path = tmp_path / "test.params.toml"
        path.write_text('version = "test"\n' + text)
        return path

    return write


def test_the_full_sequence_file_loads_against_its_model(write, sequence):
    load_parameters(write(SEQUENCE_TASKS), model=sequence)


def test_a_task_without_a_duration_is_reported_by_id(write, sequence):
    text = SEQUENCE_TASKS.replace("[tasks.Task_BuildApp]", "[tasks.Task_Other]")

    with pytest.raises(ValueError, match=r"Task_BuildApp.*no duration"):
        load_parameters(write(text), model=sequence)


def test_unknown_task_lane_and_gateway_ids_are_reported(write, sequence):
    text = SEQUENCE_TASKS + """
[tasks.Task_Typo]
duration = { fixed = 1.0 }
rationale = "Fixture value."

[lanes.Lane_Typo]
capacity = 1
rationale = "Fixture value."

[gateways.Gateway_Typo]
branches = { Flow_A = 1.0 }
rationale = "Fixture value."
"""
    with pytest.raises(ValueError) as error:
        load_parameters(write(text), model=sequence)

    message = str(error.value)
    assert "tasks.Task_Typo" in message and "lanes.Lane_Typo" in message and "gateways.Gateway_Typo" in message


def test_branches_must_name_exactly_the_outgoing_flows_of_the_split(write, fixtures_dir):
    model = read_bpmn(fixtures_dir / "book_fig7_2.bpmn")
    text = """
[tasks.Task_A]
duration = { fixed = 10.0 }
rationale = "Fixture value."

[tasks.Task_B]
duration = { fixed = 20.0 }
rationale = "Fixture value."

[tasks.Task_C]
duration = { fixed = 10.0 }
rationale = "Fixture value."

[gateways.Gateway_Split]
branches = { Flow_ToB = 0.9, Flow_ToX = 0.1 }
rationale = "Fixture value."
"""
    with pytest.raises(ValueError, match=r"Gateway_Split.*Flow_ToC"):
        load_parameters(write(text), model=model)


def test_an_xor_split_without_branches_is_reported(write, fixtures_dir):
    model = read_bpmn(fixtures_dir / "book_fig7_2.bpmn")
    text = "".join(
        f'[tasks.{task}]\nduration = {{ fixed = 1.0 }}\nrationale = "Fixture value."\n' for task in ("Task_A", "Task_B", "Task_C")
    )
    with pytest.raises(ValueError, match=r"Gateway_Split.*no branches"):
        load_parameters(write(text), model=model)


def test_simulate_checks_the_parameters_before_it_runs(write, sequence):
    params = load_parameters(write(SEQUENCE_TASKS.replace("[tasks.Task_BuildApp]", "[tasks.Task_Other]")))

    with pytest.raises(ValueError, match="Task_BuildApp"):
        simulate(sequence, params, n_cases=1, seed=1)


@pytest.mark.parametrize(
    ("entry", "where"),
    [
        ('[tasks.Task_A]\nduration = { fixed = 1.0 }\n', "tasks.Task_A"),
        ('[tasks.Task_A]\nduration = { fixed = 1.0 }\nrationale = "  "\n', "tasks.Task_A"),
        ("[lanes.Lane_Dev]\ncapacity = 1\n", "lanes.Lane_Dev"),
        ("[arrivals]\nrate = 1.0\n", "arrivals"),
        ("[gateways.Gateway_X]\nbranches = { Flow_A = 1.0 }\n", "gateways.Gateway_X"),
        ("[attributes.complexity]\ndistribution = { poisson = 1.0 }\n", "attributes.complexity"),
    ],
)
def test_an_entry_without_a_rationale_fails_validation(write, entry, where):
    with pytest.raises(ValueError, match=rf"{where}.*rationale"):
        load_parameters(write(entry))


@pytest.mark.parametrize(
    ("text", "match"),
    [
        ('[task.Task_A]\nduration = { fixed = 1.0 }\nrationale = "x"\n', r"unknown section.*task"),
        ('[tasks.Task_A]\nduraton = { fixed = 1.0 }\nrationale = "x"\n', r"tasks.Task_A.*duraton"),
        ('[attributes.case_id]\ndistribution = { poisson = 1.0 }\nrationale = "x"\n', r"attributes.case_id.*log column"),
        ('[attributes.mixed]\ndistribution = { choice = ["a", 1], weights = [0.5, 0.5] }\nrationale = "x"\n', r"attributes.mixed"),
        (
            '[gateways.G]\nbranches = { F1 = "rest", F2 = { logistic = { intercept = 0.0, size = 1.0 } } }\nrationale = "x"\n',
            r"gateways.G.branches.F2.logistic.size.*no attribute",
        ),
        (
            '[attributes.kind]\ndistribution = { choice = ["web", "app"], weights = [0.5, 0.5] }\nrationale = "x"\n'
            '[gateways.G]\nbranches = { F1 = "rest", F2 = { logistic = { kind = 1.0 } } }\nrationale = "x"\n',
            r"logistic.kind.*table of label",
        ),
        ('[gateways.G]\nbranches = { F1 = 0.3, F2 = 0.3, F3 = "rest", F4 = "rest" }\nrationale = "x"\n', r'only one branch can be "rest"'),
        (
            '[tasks.T]\nduration = { fixed = 2.0, scale = { size = 0.1 } }\nrationale = "x"\n',
            r"tasks.T.duration.scale.size.*no attribute",
        ),
        ('[tasks.T]\nduration = { fixed = 2.0, scale = 0.1 }\nrationale = "x"\n', r"tasks.T.duration.scale.*table"),
    ],
)
def test_mistakes_in_the_file_get_a_clear_error(write, text, match):
    with pytest.raises(ValueError, match=match):
        load_parameters(write(text))
