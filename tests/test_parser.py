from textwrap import dedent

from speckit_dag.parser import extract_deps, extract_files, parse_tasks


def parse(md):
    return parse_tasks(dedent(md))


def test_phases_and_tags():
    doc = parse(
        """
        # Tasks: Auth

        ## Phase 1: Setup
        - [x] T001 Create project
        - [ ] T002 [P] Configure lint

        ## Phase 2: Foundational (Blocking Prerequisites)
        - [ ] T003 Schema

        ## Phase 3: User Story 1 - Sign up (Priority: P1) 🎯 MVP
        ### Tests for User Story 1
        - [ ] T004 [P] [US1] Contract test
        ### Implementation for User Story 1
        - [ ] T005 [US1] Model

        ## Phase N: Polish & Cross-Cutting Concerns
        - [ ] T006 Docs
        """
    )
    assert doc.feature == "Auth"
    assert [(p.id, p.kind) for p in doc.phases] == [
        ("setup", "setup"),
        ("foundational", "foundational"),
        ("US1", "story"),
        ("polish", "polish"),
    ]
    us1 = doc.phases[2]
    assert (us1.story, us1.priority, us1.mvp) == ("US1", "P1", True)
    assert doc.phases[3].name == "Phase N: Polish & Cross-Cutting Concerns"

    t = {t.id: t for t in doc.tasks}
    assert t["T001"].done and not t["T002"].done
    assert t["T002"].parallel and not t["T001"].parallel
    assert t["T004"].story == "US1" and t["T004"].section == "tests"
    assert t["T005"].section == "implementation"
    assert t["T005"].section_index > t["T004"].section_index
    assert t["T004"].title == "Contract test"


def test_story_comes_from_phase_when_tag_missing():
    doc = parse(
        """
        ## Phase 3: User Story 2 - Login
        - [ ] T001 Untagged task
        """
    )
    assert doc.tasks[0].story == "US2"


def test_unknown_tags_are_kept():
    doc = parse("- [ ] T001 [P] [US1] [backend] Do it\n")
    t = doc.tasks[0]
    assert t.tags == ["backend"] and t.parallel and t.story == "US1"


def test_code_fences_are_ignored():
    doc = parse(
        """
        ## Phase 1: Setup
        - [ ] T001 Real task
        ```
        - [ ] T002 Example inside a fence
        ```
        """
    )
    assert [t.id for t in doc.tasks] == ["T001"]


def test_other_headings_become_phases_only_if_they_hold_tasks():
    doc = parse(
        """
        ## Format: `[ID] [P?] [Story] Description`
        - **[P]**: notes

        ## Backend
        - [ ] T001 Build API
        """
    )
    assert [p.name for p in doc.phases] == ["Backend"]
    assert doc.tasks[0].phase.kind == "other"


def test_tasks_without_any_heading():
    doc = parse("- [ ] T001 A\n- [ ] T002 B\n")
    assert [p.name for p in doc.phases] == ["Tasks"]
    assert len(doc.tasks) == 2


def test_duplicate_ids_warn():
    doc = parse("- [ ] T001 A\n- [ ] T001 B\n")
    assert [t.title for t in doc.tasks] == ["A"]
    assert "duplicate task id T001" in doc.warnings[0]


def test_dependencies_in_continuation_lines():
    doc = parse(
        """
        - [ ] T001 A
        - [ ] T002 B
          - Depends on T001
        - [ ] T003 C
        Not indented, after T001
        """
    )
    t = {t.id: t for t in doc.tasks}
    assert t["T002"].explicit_deps == ["T001"]
    assert t["T003"].explicit_deps == []


def test_extract_deps():
    assert extract_deps("Wire it up (depends on T012)") == ["T012"]
    assert extract_deps("after T010, T011 and T014") == ["T010", "T011", "T014"]
    assert extract_deps("blocked by T008-T010") == ["T008", "T009", "T010"]
    assert extract_deps("Depends: T3 through T5") == ["T3", "T4", "T5"]
    assert extract_deps("Mirror T012 behaviour") == []
    assert extract_deps("run after login") == []


def test_extract_files():
    text = (
        "Add `src/models/user.py`, update pyproject.toml and .eslintrc, "
        "touch ./scripts/run.sh and src/api/ for POST /signup and/or GET/POST "
        "using Node.js (e.g. src/App.js). See https://example.com/a.py, T012, v1.2, 3.x."
    )
    assert extract_files(text) == [
        "src/models/user.py",
        "pyproject.toml",
        ".eslintrc",
        "scripts/run.sh",
        "src/api/",
        "src/App.js",
    ]
