"""Graph identity: the content hash, and warnings for specs a workspace can't see."""

import json
import re
import shutil
import subprocess

import pytest

from speckit_dag import Options, group_by_story, load, to_dict
from speckit_dag.cli import main

from .helpers import EXAMPLE, ROOT, SCHEMA

TEXT = EXAMPLE.read_text(encoding="utf-8")


def graph_hash(tmp_path, text, name="001-user-auth", unit="task", **opts):
    folder = tmp_path / name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "tasks.md").write_text(text, encoding="utf-8")
    g = load(folder, Options(**opts), use_git=False)
    return to_dict(group_by_story(g) if unit == "story" else g)["hash"]


def test_hash_format(tmp_path):
    h = graph_hash(tmp_path, TEXT)
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", h)


def test_same_tasks_same_hash_anywhere(tmp_path):
    # Different folder, no git, versus the real example inside the repo.
    assert graph_hash(tmp_path, TEXT, name="elsewhere") == to_dict(load(EXAMPLE))["hash"]


def test_progress_and_line_shifts_keep_the_hash(tmp_path):
    base = graph_hash(tmp_path / "a", TEXT)
    ticked = TEXT.replace("- [ ] T002", "- [x] T002").replace("- [ ] T012", "- [x] T012")
    assert graph_hash(tmp_path / "b", ticked) == base
    assert graph_hash(tmp_path / "c", "\n\n" + TEXT) == base


def test_changed_work_changes_the_hash(tmp_path):
    base = graph_hash(tmp_path / "a", TEXT)
    retitled = TEXT.replace("Create User model", "Create Account model")
    new_note = TEXT.replace("  - Return a 409", "  - Log the attempt\n  - Return a 409")
    new_goal = TEXT.replace("**Goal**: A visitor can create", "**Goal**: Anyone can create")
    new_dep = TEXT.replace("in src/api/reset.py", "in src/api/reset.py (after T013)")
    hashes = {
        graph_hash(tmp_path / "b", retitled),
        graph_hash(tmp_path / "c", new_note),
        graph_hash(tmp_path / "d", new_goal),
        graph_hash(tmp_path / "e", new_dep),
        graph_hash(tmp_path / "f", TEXT, sequential_stories=True),
        graph_hash(tmp_path / "g", TEXT, unit="story"),
    }
    assert base not in hashes and len(hashes) == 6


def test_unit_hash_ignores_progress(tmp_path):
    base = graph_hash(tmp_path / "a", TEXT, unit="story")
    ticked = TEXT.replace("- [ ] T008", "- [x] T008")
    assert graph_hash(tmp_path / "b", ticked, unit="story") == base


def test_schema_accepts_identity_fields():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    d = to_dict(load(EXAMPLE))
    jsonschema.validate(d, schema)
    assert set(d["spec"]) >= {"commit", "dirty", "pushed"}


# Warnings for graphs a workspace cloned from the remote couldn't reproduce


def git(cwd, *args):
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
        cwd=cwd, check=True, capture_output=True, text=True,
    ).stdout


@pytest.fixture
def pushed_repo(tmp_path):
    if shutil.which("git") is None:
        pytest.skip("git is not available")
    remote, work = tmp_path / "remote.git", tmp_path / "work"
    git(tmp_path, "init", "-q", "--bare", str(remote))
    folder = work / "specs" / "003-search"
    folder.mkdir(parents=True)
    (folder / "tasks.md").write_text("## Phase 1: Setup\n- [ ] T001 A\n- [ ] T002 B\n", encoding="utf-8")
    git(work, "init", "-q", "-b", "main")
    git(work, "remote", "add", "origin", str(remote))
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "spec")
    git(work, "push", "-q", "-u", "origin", "main")
    return work


def run_json(capsys, *args):
    code = main(list(args))
    out = capsys.readouterr()
    return code, (json.loads(out.out) if out.out else None), out.err


def test_clean_and_pushed(pushed_repo, capsys):
    code, d, err = run_json(capsys, str(pushed_repo / "specs" / "003-search"), "--strict")
    assert code == 0 and err == ""
    assert d["spec"]["dirty"] is False and d["spec"]["pushed"] is True
    assert d["warnings"] == []


def test_uncommitted_changes_fail_strict(pushed_repo, capsys):
    folder = pushed_repo / "specs" / "003-search"
    (folder / "tasks.md").write_text("## Phase 1: Setup\n- [x] T001 A\n- [ ] T002 B\n", encoding="utf-8")
    (folder / "plan.md").write_text("# Plan\n", encoding="utf-8")
    code, d, err = run_json(capsys, str(folder), "--strict")
    assert code == 1
    assert d["spec"]["dirty"] is True
    assert "specs/003-search has changes that aren't committed" in err
    assert "specs/003-search/tasks.md" in err and "specs/003-search/plan.md" in err


def test_changes_outside_the_spec_folder_are_ignored(pushed_repo, capsys):
    (pushed_repo / "README.md").write_text("unrelated\n", encoding="utf-8")
    code, d, _ = run_json(capsys, str(pushed_repo / "specs" / "003-search"), "--strict")
    assert code == 0 and d["spec"]["dirty"] is False


def test_unpushed_commit_fails_strict(pushed_repo, capsys):
    folder = pushed_repo / "specs" / "003-search"
    (folder / "tasks.md").write_text("## Phase 1: Setup\n- [ ] T001 A\n", encoding="utf-8")
    git(pushed_repo, "commit", "-q", "-am", "edit")
    code, d, err = run_json(capsys, str(folder), "--strict")
    assert code == 1
    assert d["spec"]["pushed"] is False and d["spec"]["dirty"] is False
    assert "isn't on origin yet" in err


def test_no_origin_and_no_repo(tmp_path, capsys):
    if shutil.which("git") is None:
        pytest.skip("git is not available")
    lone = tmp_path / "lone"
    (lone / "specs" / "x").mkdir(parents=True)
    (lone / "specs" / "x" / "tasks.md").write_text("- [ ] T001 A\n", encoding="utf-8")
    git(lone, "init", "-q")
    code, d, err = run_json(capsys, str(lone / "specs" / "x"), "--strict")
    assert code == 1 and "no commits yet" in err
    git(lone, "add", ".")
    git(lone, "commit", "-q", "-m", "x")
    code, d, err = run_json(capsys, str(lone / "specs" / "x"), "--strict")
    assert code == 1 and "no origin remote" in err and d["spec"]["pushed"] is False

    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "tasks.md").write_text("- [ ] T001 A\n", encoding="utf-8")
    code, d, err = run_json(capsys, str(plain), "--strict")
    assert code == 1 and "isn't in a git repository" in err
    assert d["spec"]["commit"] is None
    # --no-git skips every check.
    code, _, err = run_json(capsys, str(plain), "--strict", "--no-git")
    assert code == 0 and err == ""


def test_source_is_relative_to_the_repo_root(monkeypatch, capsys):
    monkeypatch.chdir(ROOT / "examples")
    code, d, _ = run_json(capsys, "specs/001-user-auth", "-q")
    assert code == 0
    assert d["source"] == "examples/specs/001-user-auth/tasks.md"
    assert d["source"] == d["spec"]["tasks"]
    assert d["spec"]["dir"] == "examples/specs/001-user-auth"
