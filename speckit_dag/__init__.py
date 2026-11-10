"""Build a dependency graph (DAG) from Spec Kit tasks.md files."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

from .emit import FORMATS, to_dict, to_dot, to_json, to_mermaid, to_yaml
from .graph import CycleError, ready, topo_order, waves
from .model import Graph, ParsedDoc, Phase, Task
from .parser import parse_tasks
from .rules import Options, build_graph

__version__ = "0.1.0"


def load(path: Union[str, Path], options: Optional[Options] = None) -> Graph:
    """Parse a tasks.md (or a spec folder containing one) and build its graph."""
    path = Path(path)
    if path.is_dir():
        path = path / "tasks.md"
    doc = parse_tasks(path.read_text(encoding="utf-8"), source=str(path))
    return build_graph(doc, options)


__all__ = [
    "CycleError",
    "FORMATS",
    "Graph",
    "Options",
    "ParsedDoc",
    "Phase",
    "Task",
    "build_graph",
    "load",
    "parse_tasks",
    "ready",
    "to_dict",
    "to_dot",
    "to_json",
    "to_mermaid",
    "to_yaml",
    "topo_order",
    "waves",
]
