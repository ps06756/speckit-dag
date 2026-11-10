import pytest

from speckit_dag import CycleError, waves

from .helpers import build, edges


def test_parallel_run_hangs_off_previous_task():
    g = build(
        """
        - [ ] T001 A
        - [ ] T002 [P] B
        - [ ] T003 [P] C
        - [ ] T004 D
        """
    )
    assert edges(g) == {("T001", "T002"), ("T001", "T003"), ("T002", "T004"), ("T003", "T004")}
    assert g.edges[("T001", "T002")] == {"sequence"}


def test_parallel_tasks_at_start_have_no_predecessors():
    g = build(
        """
        - [ ] T001 [P] A
        - [ ] T002 [P] B
        """
    )
    assert edges(g) == set()
    assert waves(g) == [["T001", "T002"]]


def test_sections_run_in_order():
    g = build(
        """
        ## Phase 3: User Story 1 - X
        ### Tests for User Story 1
        - [ ] T001 [P] [US1] Test A
        - [ ] T002 [P] [US1] Test B
        ### Implementation for User Story 1
        - [ ] T003 [P] [US1] Model
        - [ ] T004 [US1] Service
        """
    )
    assert edges(g) == {
        ("T001", "T003"),
        ("T002", "T003"),
        ("T003", "T004"),
    }
    assert g.edges[("T001", "T003")] == {"section"}


def test_phase_barriers_and_parallel_stories():
    g = build(
        """
        ## Phase 1: Setup
        - [ ] T001 Setup
        ## Phase 2: Foundational
        - [ ] T002 Base
        ## Phase 3: User Story 1 - A
        - [ ] T003 [US1] A1
        - [ ] T004 [US1] A2
        ## Phase 4: User Story 2 - B
        - [ ] T005 [US2] B1
        ## Phase 5: Polish
        - [ ] T006 Docs
        """
    )
    assert edges(g) == {
        ("T001", "T002"),
        ("T002", "T003"),
        ("T002", "T005"),
        ("T003", "T004"),
        ("T004", "T006"),
        ("T005", "T006"),
    }
    assert g.edges[("T002", "T005")] == {"phase"}
    assert waves(g) == [["T001"], ["T002"], ["T003", "T005"], ["T004"], ["T006"]]


def test_sequential_stories():
    g = build(
        """
        ## Phase 3: User Story 1 - A
        - [ ] T001 [US1] A
        ## Phase 4: User Story 2 - B
        - [ ] T002 [US2] B
        """,
        sequential_stories=True,
    )
    assert edges(g) == {("T001", "T002")}


def test_phase_edges_link_every_end_to_every_start():
    g = build(
        """
        ## Phase 1: Setup
        - [ ] T001 [P] A
        - [ ] T002 [P] B
        ## Phase 2: Foundational
        - [ ] T003 [P] C
        - [ ] T004 [P] D
        """
    )
    assert edges(g) == {("T001", "T003"), ("T001", "T004"), ("T002", "T003"), ("T002", "T004")}


def test_explicit_dependency_across_stories():
    g = build(
        """
        ## Phase 3: User Story 1 - A
        - [ ] T001 [US1] Model in src/models/user.py
        - [ ] T002 [US1] Endpoint
        ## Phase 4: User Story 2 - B
        - [ ] T003 [US2] Uses the model (depends on T001)
        """
    )
    assert edges(g) == {("T001", "T002"), ("T001", "T003")}
    assert g.edges[("T001", "T003")] == {"explicit"}


def test_unknown_and_self_dependencies_warn():
    g = build(
        """
        - [ ] T001 A (depends on T001)
        - [ ] T002 B (depends on T099)
        """
    )
    assert any("T001 lists itself" in w for w in g.warnings)
    assert any("unknown task T099" in w for w in g.warnings)


def test_file_conflicts_order_parallel_tasks():
    md = """
        - [ ] T001 [P] Add field in src/models/user.py
        - [ ] T002 [P] Add index in src/models/user.py
        """
    g = build(md)
    assert edges(g) == {("T001", "T002")}
    assert g.edges[("T001", "T002")] == {"file"}
    assert edges(build(md, file_conflicts=False)) == set()


def test_file_conflict_between_stories_warns():
    g = build(
        """
        ## Phase 3: User Story 1 - A
        - [ ] T001 [US1] Edit src/app.py
        ## Phase 4: User Story 2 - B
        - [ ] T002 [US2] Edit src/app.py
        """
    )
    assert edges(g) == {("T001", "T002")}
    assert any("US1 and US2 both touch src/app.py" in w for w in g.warnings)


def test_directories_do_not_conflict():
    g = build(
        """
        - [ ] T001 [P] Create src/models/
        - [ ] T002 [P] Create src/models/
        """
    )
    assert edges(g) == set()


def test_cycle_is_reported():
    with pytest.raises(CycleError) as err:
        build(
            """
            - [ ] T001 A (depends on T002)
            - [ ] T002 B
            """
        )
    assert err.value.cycle in (["T001", "T002", "T001"], ["T002", "T001", "T002"])


def test_reduction_can_be_turned_off():
    md = """
        - [ ] T001 A
        - [ ] T002 B
        - [ ] T003 C (depends on T001)
        """
    assert ("T001", "T003") not in build(md).edges
    assert build(md, reduce=False).edges[("T001", "T003")] == {"explicit"}


def test_merged_reasons():
    g = build(
        """
        - [ ] T001 A
        - [ ] T002 B (after T001)
        """
    )
    assert g.edges[("T001", "T002")] == {"sequence", "explicit"}


def test_example_file(example_graph):
    g = example_graph
    assert len(g.tasks) == 21
    assert g.warnings == []
    assert ("T011", "T017") in g.edges           # explicit, crosses stories
    assert ("T007", "T017") not in g.edges       # implied via T011, so removed
    assert ("T007", "T014") in g.edges           # stories start after Foundational
    w = waves(g)
    assert w[0] == ["T001"]
    assert w[5] == ["T008", "T009", "T014"]
    assert w[-1] == ["T021"]
