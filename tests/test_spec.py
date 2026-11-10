"""Task text, section text, and where the spec folder lives."""

import json
import subprocess
from textwrap import dedent

import pytest

from speckit_dag import group_by_story, load, locate_spec, parse_tasks, to_dict
from speckit_dag.cli import main

from .helpers import EXAMPLE, SCHEMA


def parse(md):
    return parse_tasks(dedent(md))


def test_task_text_includes_indented_lines_and_code():
    doc = parse(
        """
        ## Phase 1: Setup
        - [ ] T001 Add config loader in src/config.py
          - Read env vars first, then config.toml

          - Fail fast on unknown keys
          ```toml
          [db]
          url = "postgres://localhost/app"
          ```
        - [ ] T002 Next task
        Not part of T002
        """
    )
    t1, t2 = doc.tasks
    assert t1.text == dedent(
        """\
        - [ ] T001 Add config loader in src/config.py
          - Read env vars first, then config.toml

          - Fail fast on unknown keys
          ```toml
          [db]
          url = "postgres://localhost/app"
          ```"""
    )
    assert (t1.line, t1.end_line) == (3, 10)
    assert t2.text == "- [ ] T002 Next task"
    assert t2.end_line == t2.line


def test_nested_task_text_is_dedented():
    doc = parse(
        """
        - Backend
          - [ ] T001 Build API
            - Use the existing router
        """
    )
    assert doc.tasks[0].text == "- [ ] T001 Build API\n  - Use the existing router"


def test_code_block_under_a_task_still_hides_tasks_inside_it():
    doc = parse(
        """
        - [ ] T001 Document the format
          ```
          - [ ] T999 example line
          ```
        """
    )
    assert [t.id for t in doc.tasks] == ["T001"]
    assert "T999" in doc.tasks[0].text


def test_section_text_runs_to_the_next_heading():
    doc = parse(
        """
        ## Phase 1: Setup

        **Goal**: Get the repo ready.

        - [ ] T001 A

        ---

        ## Phase 2: Foundational
        - [ ] T002 B
        ## Notes
        Not part of any phase.
        """
    )
    setup, found = doc.phases
    assert setup.text == "## Phase 1: Setup\n\n**Goal**: Get the repo ready.\n\n- [ ] T001 A"
    assert (setup.line, setup.end_line) == (2, 6)
    assert found.text == "## Phase 2: Foundational\n- [ ] T002 B"


def test_example_spec_folder():
    spec = locate_spec(EXAMPLE)
    assert spec.id == "001-user-auth"
    assert spec.dir == "examples/specs/001-user-auth"
    assert spec.tasks == "examples/specs/001-user-auth/tasks.md"
    assert spec.docs == {
        "spec": "examples/specs/001-user-auth/spec.md",
        "plan": "examples/specs/001-user-auth/plan.md",
        "data-model": "examples/specs/001-user-auth/data-model.md",
    }
    assert spec.ref("T010") == "examples/specs/001-user-auth/tasks.md#T010"


def _git(cwd, *args):
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
        cwd=cwd, check=True, capture_output=True,
    )


@pytest.fixture
def repo(tmp_path):
    folder = tmp_path / "specs" / "002-billing"
    (folder / "contracts").mkdir(parents=True)
    (folder / "tasks.md").write_text("## Phase 1: Setup\n- [ ] T001 A\n", encoding="utf-8")
    (folder / "spec.md").write_text("# Spec\n", encoding="utf-8")
    try:
        _git(tmp_path, "init", "-q", "-b", "002-billing")
        _git(tmp_path, "remote", "add", "origin", "https://user:secret@github.com/acme/app.git")
        _git(tmp_path, "add", ".")
        _git(tmp_path, "commit", "-q", "-m", "init")
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("git is not available")
    return tmp_path


def test_git_state(repo):
    spec = locate_spec(repo / "specs" / "002-billing" / "tasks.md")
    assert spec.dir == "specs/002-billing"
    assert spec.docs == {"spec": "specs/002-billing/spec.md", "contracts": "specs/002-billing/contracts/"}
    assert spec.repo == "https://github.com/acme/app.git"  # credentials removed
    assert spec.branch == "002-billing"
    assert len(spec.commit) == 40
    assert spec.dirty is False

    (repo / "specs" / "002-billing" / "tasks.md").write_text("- [ ] T001 changed\n", encoding="utf-8")
    assert locate_spec(repo / "specs" / "002-billing" / "tasks.md").dirty is True


def test_without_git(repo, monkeypatch):
    monkeypatch.chdir(repo / "specs")
    spec = locate_spec(repo / "specs" / "002-billing" / "tasks.md", use_git=False)
    assert spec.tasks == "002-billing/tasks.md"
    assert (spec.repo, spec.branch, spec.commit, spec.dirty) == (None, None, None, None)


def test_load_fills_spec_and_refs():
    g = load(EXAMPLE, use_git=False)
    d = to_dict(g)
    assert d["spec"]["id"] == "001-user-auth"
    t012 = next(n for n in d["nodes"] if n["id"] == "T012")
    assert t012["ref"].endswith("001-user-auth/tasks.md#T012")
    assert t012["text"].splitlines()[1] == "  - Hash the password with the helpers in src/lib/crypto.py"
    us1 = next(gr for gr in d["groups"] if gr["id"] == "US1")
    assert us1["text"].startswith("## Phase 3: User Story 1")
    assert "**Goal**: A visitor can create an account" in us1["text"]


def test_units_carry_section_text_and_task_refs():
    d = to_dict(group_by_story(load(EXAMPLE, use_git=False)))
    us1 = next(n for n in d["nodes"] if n["id"] == "US1")
    assert "**Goal**: A visitor can create an account" in us1["text"]
    assert (us1["line"], us1["end_line"]) == (36, 53)
    assert all(t["ref"].endswith("#" + t["id"]) for t in us1["tasks"])
    assert d["spec"]["docs"]["spec"].endswith("001-user-auth/spec.md")


def test_output_matches_schema():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    g = load(EXAMPLE)
    jsonschema.validate(to_dict(g), schema)
    jsonschema.validate(to_dict(group_by_story(g)), schema)


def test_cli_records_spec(capsys, repo):
    assert main([str(repo / "specs" / "002-billing")]) == 0
    d = json.loads(capsys.readouterr().out)
    assert d["spec"]["branch"] == "002-billing"
    assert d["nodes"][0]["ref"] == "specs/002-billing/tasks.md#T001"

    assert main([str(repo / "specs" / "002-billing"), "--no-git"]) == 0
    assert json.loads(capsys.readouterr().out)["spec"]["commit"] is None
