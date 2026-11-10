import json

import pytest

from speckit_dag import to_dict, to_dot, to_mermaid
from speckit_dag.emit import to_ready_text, to_waves_text, to_yaml

from .helpers import SCHEMA, build


def test_dict_shape(example_graph):
    d = to_dict(example_graph)
    assert d["version"] == 1
    assert d["feature"] == "User Authentication"
    assert [g["id"] for g in d["groups"]] == ["setup", "foundational", "US1", "US2", "US3", "polish"]
    node = next(n for n in d["nodes"] if n["id"] == "T010")
    assert node == {
        "id": "T010",
        "title": "Create User model in src/models/user.py",
        "group": "US1",
        "section": "implementation",
        "parallel": True,
        "story": "US1",
        "files": ["src/models/user.py"],
        "status": "todo",
        "line": node["line"],
        "tags": [],
    }
    assert {"from": "T011", "to": "T017", "reasons": ["explicit"]} in d["edges"]


def test_matches_schema(example_graph):
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.validate(to_dict(example_graph), schema)


def test_yaml_round_trip(example_graph):
    yaml = pytest.importorskip("yaml")
    assert yaml.safe_load(to_yaml(example_graph)) == to_dict(example_graph)


def test_mermaid(example_graph):
    out = to_mermaid(example_graph)
    assert out.startswith("flowchart TD\n")
    assert '  subgraph g_US1["Phase 3: User Story 1' in out
    assert "  T001 --> T002\n" in out
    assert "  T011 -.-> T017\n" in out  # explicit-only edges are dashed
    assert "  class T001 done\n" in out


def test_mermaid_escapes_quotes_and_truncates():
    g = build('- [ ] T001 Say "hello" ' + "x" * 100 + "\n")
    out = to_mermaid(g, max_label=30)
    assert "#quot;hello#quot;" in out
    assert "…" in out


def test_dot(example_graph):
    out = to_dot(example_graph)
    assert out.startswith('digraph "User Authentication" {')
    assert 'subgraph "cluster_US1"' in out
    assert '"T011" -> "T017" [tooltip="explicit", style=dashed];' in out
    assert out.rstrip().endswith("}")


def test_waves_and_ready(example_graph):
    waves = to_waves_text(example_graph)
    assert waves.startswith("Wave 1:\n  [x] T001  Create project structure")
    assert to_ready_text(example_graph) == (
        "T002\tConfigure ruff and black in pyproject.toml\n"
        "T003\tAdd CI workflow in .github/workflows/ci.yml\n"
    )
