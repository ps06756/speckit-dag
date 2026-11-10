import io
import json

from speckit_dag.cli import main

from .helpers import EXAMPLE


def test_json_to_stdout(capsys):
    assert main([str(EXAMPLE)]) == 0
    d = json.loads(capsys.readouterr().out)
    assert len(d["nodes"]) == 21


def test_spec_folder_and_output_file(tmp_path):
    (tmp_path / "tasks.md").write_text("- [ ] T001 A\n- [ ] T002 B\n", encoding="utf-8")
    out = tmp_path / "graph.mmd"
    assert main([str(tmp_path), "-f", "mermaid", "-o", str(out)]) == 0
    assert "T001 --> T002" in out.read_text(encoding="utf-8")


def test_stdin(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("- [ ] T001 A\n"))
    assert main(["-", "-f", "ready"]) == 0
    assert capsys.readouterr().out == "T001\tA\n"


def test_warnings_and_strict(tmp_path, capsys):
    f = tmp_path / "tasks.md"
    f.write_text("- [ ] T001 A (depends on T099)\n", encoding="utf-8")
    assert main([str(f), "-f", "ready"]) == 0
    assert "unknown task T099" in capsys.readouterr().err
    assert main([str(f), "-f", "ready", "--strict", "-q"]) == 1
    assert capsys.readouterr().err == ""


def test_cycle_exits_with_error(tmp_path, capsys):
    f = tmp_path / "tasks.md"
    f.write_text("- [ ] T001 A (after T002)\n- [ ] T002 B\n", encoding="utf-8")
    assert main([str(f)]) == 1
    assert "dependency cycle" in capsys.readouterr().err


def test_missing_file_and_empty_file(tmp_path, capsys):
    assert main([str(tmp_path / "nope.md")]) == 1
    empty = tmp_path / "empty.md"
    empty.write_text("# Nothing here\n", encoding="utf-8")
    assert main([str(empty)]) == 1
    assert "no tasks found" in capsys.readouterr().err
