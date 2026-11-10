"""Build a dependency graph (DAG) from Spec Kit tasks.md files."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

from .emit import FORMATS, to_dict, to_dot, to_json, to_mermaid, to_yaml
from .graph import CycleError, ready, topo_order, waves
from .model import Graph, ParsedDoc, Phase, SpecInfo, Task, Unit, UnitGraph
from .parser import parse_tasks
from .rules import Options, build_graph
from .identity import content_hash
from .spec import attach_spec, locate_spec
from .units import group_by_story

__version__ = "0.1.0"


def load(path: Union[str, Path], options: Optional[Options] = None, use_git: bool = True) -> Graph:
    """Parse a tasks.md (or a spec folder containing one) and build its graph."""
    path = Path(path)
    if path.is_dir():
        path = path / "tasks.md"
    doc = parse_tasks(path.read_text(encoding="utf-8"), source=str(path))
    attach_spec(doc, path, use_git=use_git)
    return build_graph(doc, options)


__all__ = [
    "CycleError",
    "FORMATS",
    "Graph",
    "Options",
    "ParsedDoc",
    "Phase",
    "SpecInfo",
    "Task",
    "Unit",
    "UnitGraph",
    "attach_spec",
    "build_graph",
    "content_hash",
    "group_by_story",
    "load",
    "locate_spec",
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
