import json
from textwrap import dedent

import pytest

from speckit_dag import CycleError, group_by_story, ready, to_dict, waves
from speckit_dag.cli import main
from speckit_dag.emit import to_dot, to_mermaid, to_waves_text

from .helpers import EXAMPLE, SCHEMA, build, edges


@pytest.fixture
def units(example_graph):
    return group_by_story(example_graph)


def test_one_unit_per_phase(units):
    assert [u.id for u in units.nodes] == ["setup", "foundational", "US1", "US2", "US3", "polish"]
    assert units.by_id["US1"].title == "User Story 1 - Sign up with email"
    assert units.by_id["setup"].title == "Setup (Shared Infrastructure)"


def test_tests_ship_with_the_code_that_makes_them_pass(units):
    # T008/T009 are the sign-up tests; T010-T013 make them pass. One node, in order.
    assert [t.id for t in units.by_id["US1"].tasks] == ["T008", "T009", "T010", "T011", "T012", "T013"]


def test_unit_edges_and_waves(units):
    assert edges(units) == {
        ("setup", "foundational"),
        ("foundational", "US1"),
        ("foundational", "US2"),
        ("US1", "US3"),        # T017 depends on T011
        ("US2", "polish"),
        ("US3", "polish"),     # US1 -> polish is implied through US3
    }
    assert units.via[("US1", "US3")] == [("T011", "T017")]
    assert units.edges[("US1", "US3")] == {"explicit"}
    assert waves(units) == [["setup"], ["foundational"], ["US1", "US2"], ["US3"], ["polish"]]


def test_no_reduce_keeps_implied_unit_edges(example_graph):
    ug = group_by_story(example_graph, reduce=False)
    assert ("US1", "polish") in ug.edges
    assert ug.via[("US1", "polish")] == [("T013", "T019"), ("T013", "T020")]


def test_status_and_ready(units):
    assert units.by_id["setup"].status == "in_progress"  # T001 is done, T002/T003 aren't
    assert units.by_id["US1"].status == "todo"
    assert ready(units) == ["setup"]


def test_unit_done_when_all_tasks_done():
    ug = group_by_story(build(
        """
        ## Phase 1: Setup
        - [x] T001 A
        - [x] T002 B
        ## Phase 2: Foundational
        - [ ] T003 C
        """
    ))
    assert ug.by_id["setup"].status == "done"
    assert ready(ug) == ["foundational"]


def test_sequential_stories_chain_units(example_graph):
    g = build(EXAMPLE.read_text(encoding="utf-8"), sequential_stories=True)
    ug = group_by_story(g)
    assert ("US1", "US2") in ug.edges and ("US2", "US3") in ug.edges
    assert waves(ug) == [["setup"], ["foundational"], ["US1"], ["US2"], ["US3"], ["polish"]]


CROSSED = """
    ## Phase 3: User Story 1 - A
    - [ ] T001 [US1] Shared model
    - [ ] T002 [US1] Endpoint (depends on T004)
    ## Phase 4: User Story 2 - B
    - [ ] T003 [US2] Service (depends on T001)
    - [ ] T004 [US2] Client
    """


def test_stories_that_depend_on_each_other_are_a_cycle():
    g = build(CROSSED)  # fine as tasks: T001 -> T003 -> T004 -> T002
    with pytest.raises(CycleError) as err:
        group_by_story(g)
    msg = str(err.value)
    assert err.value.cycle in (["US1", "US2", "US1"], ["US2", "US1", "US2"])
    assert "US2 needs US1 because of T001 -> T003" in msg
    assert "US1 needs US2 because of T004 -> T002" in msg


def test_story_tag_outside_its_phase_warns():
    ug = group_by_story(build(
        """
        ## Phase 3: User Story 1 - A
        - [ ] T001 [US1] A
        ## Phase 4: Polish
        - [ ] T002 [US1] Follow-up for story 1
        """
    ))
    assert any("T002 is tagged US1 but sits in polish" in w for w in ug.warnings)


def test_dict_shape(units):
    d = to_dict(units)
    assert d["unit"] == "story"
    us1 = next(n for n in d["nodes"] if n["id"] == "US1")
    assert us1["kind"] == "story" and us1["priority"] == "P1" and us1["mvp"] is True
    assert us1["status"] == "todo"
    assert us1["line"] == 36
    assert [t["id"] for t in us1["tasks"]][:2] == ["T008", "T009"]
    assert "src/models/user.py" in us1["files"]
    assert {"from": "US1", "to": "US3", "reasons": ["explicit"], "via": [{"from": "T011", "to": "T017"}]} in d["edges"]


def test_task_mode_says_unit_task(example_graph):
    assert to_dict(example_graph)["unit"] == "task"


def test_unit_graph_matches_schema(units):
    jsonschema = pytest.importorskip("jsonschema")
    jsonschema.validate(to_dict(units), json.loads(SCHEMA.read_text(encoding="utf-8")))


def test_text_formats(units):
    assert "  u_US1 -.-> u_US3\n" in to_mermaid(units)
    assert "  class u_setup partial\n" in to_mermaid(units)
    assert '"US1" -> "US3" [tooltip="explicit", style=dashed];' in to_dot(units)
    assert "  [~] setup  Setup (Shared Infrastructure)  (3 tasks, 1 done)\n" in to_waves_text(units)


def test_cli(tmp_path, capsys):
    assert main([str(EXAMPLE), "--unit", "story", "-f", "ready"]) == 0
    assert capsys.readouterr().out == "setup\tSetup (Shared Infrastructure)\n"

    f = tmp_path / "tasks.md"
    f.write_text(dedent(CROSSED), encoding="utf-8")
    assert main([str(f), "-f", "ready", "-q"]) == 0          # fine as tasks
    capsys.readouterr()
    assert main([str(f), "--unit", "story"]) == 1             # not as stories
    assert "grouping by story creates a cycle" in capsys.readouterr().err
