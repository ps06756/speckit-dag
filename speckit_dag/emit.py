"""Output formats: the generic JSON/YAML graph, Mermaid, Graphviz DOT, and text views.

Every format works for both graph types: one node per task (`Graph`) and one
node per unit of work (`UnitGraph`).
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Dict, List, Optional, Union

from .graph import ready, waves
from .model import Graph, Phase, SpecInfo, Task, Unit, UnitGraph

FORMAT_VERSION = 1

AnyGraph = Union[Graph, UnitGraph]


def to_dict(g: AnyGraph) -> Dict[str, Any]:
    """The generic graph format (see schema/speckit-dag.schema.json)."""
    if isinstance(g, UnitGraph):
        nodes = [_unit_dict(u, g.spec) for u in g.nodes]
        edges = [
            {"from": a, "to": b, "reasons": r, "via": [{"from": x, "to": y} for x, y in g.via[(a, b)]]}
            for a, b, r in g.sorted_edges()
        ]
        groups = [_group_dict(u.phase) for u in g.nodes]
        unit = g.by
    else:
        nodes = [_task_dict(t, g.spec) for t in g.tasks]
        edges = [{"from": a, "to": b, "reasons": r} for a, b, r in g.sorted_edges()]
        groups = [_group_dict(p) for p in g.phases_with_tasks()]
        unit = "task"
    return {
        "version": FORMAT_VERSION,
        "unit": unit,
        "feature": g.feature,
        "source": g.source,
        "spec": _spec_dict(g.spec),
        "groups": groups,
        "nodes": nodes,
        "edges": edges,
        "waves": waves(g),
        "warnings": g.warnings,
    }


def _group_dict(p: Phase) -> Dict[str, Any]:
    return {
        "id": p.id,
        "name": p.name,
        "kind": p.kind,
        "order": p.index,
        "story": p.story,
        "priority": p.priority,
        "mvp": p.mvp,
        "line": p.line,
        "end_line": p.end_line,
        "text": p.text,
    }


def _spec_dict(spec: Optional[SpecInfo]) -> Optional[Dict[str, Any]]:
    if spec is None:
        return None
    return {
        "id": spec.id,
        "dir": spec.dir,
        "tasks": spec.tasks,
        "docs": spec.docs,
        "repo": spec.repo,
        "branch": spec.branch,
        "commit": spec.commit,
        "dirty": spec.dirty,
    }


def _task_dict(t: Task, spec: Optional[SpecInfo]) -> Dict[str, Any]:
    return {
        "id": t.id,
        "title": t.title,
        "group": t.phase.id,
        "section": t.section,
        "parallel": t.parallel,
        "story": t.story,
        "files": t.files,
        "status": t.status,
        "ref": spec.ref(t.id) if spec else None,
        "line": t.line,
        "end_line": t.end_line,
        "tags": t.tags,
        "text": t.text,
    }


def _unit_dict(u: Unit, spec: Optional[SpecInfo]) -> Dict[str, Any]:
    p = u.phase
    return {
        "id": u.id,
        "title": u.title,
        "group": u.id,
        "kind": u.kind,
        "story": p.story,
        "priority": p.priority,
        "mvp": p.mvp,
        "files": u.files,
        "status": u.status,
        "line": p.line,
        "end_line": p.end_line,
        "text": p.text,
        "tasks": [_task_dict(t, spec) for t in u.tasks],
    }


def to_json(g: AnyGraph) -> str:
    return json.dumps(to_dict(g), indent=2, ensure_ascii=False) + "\n"


def to_yaml(g: AnyGraph) -> str:
    try:
        import yaml
    except ImportError as e:  # pragma: no cover - depends on the environment
        raise RuntimeError("YAML output needs PyYAML: pip install 'speckit-dag[yaml]'") from e
    return yaml.safe_dump(to_dict(g), sort_keys=False, allow_unicode=True)


def to_mermaid(g: AnyGraph, max_label: int = 60) -> str:
    lines = ["flowchart TD"]
    if isinstance(g, UnitGraph):
        ids = {u.id: "u_" + _safe_id(u.id) for u in g.nodes}
        for u in g.nodes:
            label = f"{u.id} · {_trunc(u.title, max_label)}<br/>{_count(u)}"
            lines.append(f'  {ids[u.id]}["{_mermaid_text(label)}"]')
    else:
        ids = {t.id: t.id for t in g.tasks}
        for p in g.phases_with_tasks():
            lines.append(f'  subgraph g_{_safe_id(p.id)}["{_mermaid_text(p.name)}"]')
            for t in g.tasks_in(p):
                lines.append(f'    {t.id}["{_mermaid_text(t.id + " " + _trunc(t.title, max_label))}"]')
            lines.append("  end")
    for a, b, reasons in g.sorted_edges():
        arrow = "-.->" if reasons == ["explicit"] else "-->"
        lines.append(f"  {ids[a]} {arrow} {ids[b]}")

    lines.append("  classDef done fill:#dcfce7,stroke:#16a34a,color:#14532d")
    lines.append("  classDef partial fill:#fef9c3,stroke:#ca8a04,color:#713f12")
    lines.append("  classDef parallel stroke-dasharray:4 3")
    done = [ids[n.id] for n in g.nodes if n.status == "done"]
    partial = [ids[n.id] for n in g.nodes if n.status == "in_progress"]
    parallel = [ids[n.id] for n in g.nodes if getattr(n, "parallel", False)]
    for cls, members in (("done", done), ("partial", partial), ("parallel", parallel)):
        if members:
            lines.append(f"  class {','.join(members)} {cls}")
    return "\n".join(lines) + "\n"


def to_dot(g: AnyGraph, max_label: int = 60) -> str:
    lines = [
        f"digraph {_dot_str(g.feature or 'tasks')} {{",
        "  rankdir=TB;",
        '  node [shape=box, style=rounded, fontname="Helvetica", fontsize=10];',
        "  edge [color=\"#64748b\"];",
    ]
    if isinstance(g, UnitGraph):
        for u in g.nodes:
            lines.append(f"  {_dot_node(u, u.id + chr(10) + _trunc(u.title, max_label) + chr(10) + _count(u))}")
    else:
        for p in g.phases_with_tasks():
            lines.append(f"  subgraph {_dot_str('cluster_' + p.id)} {{")
            lines.append(f"    label={_dot_str(p.name)}; style=rounded; color=\"#cbd5e1\";")
            for t in g.tasks_in(p):
                lines.append(f"    {_dot_node(t, t.id + chr(10) + _trunc(t.title, max_label))}")
            lines.append("  }")
    for a, b, reasons in g.sorted_edges():
        extra = ", style=dashed" if reasons == ["explicit"] else ""
        lines.append(f"  {_dot_str(a)} -> {_dot_str(b)} [tooltip={_dot_str(','.join(reasons))}{extra}];")
    lines.append("}")
    return "\n".join(lines) + "\n"


def _dot_node(n: Union[Task, Unit], label: str) -> str:
    style = ["rounded"]
    attrs = [f"label={_dot_str(label)}"]
    if getattr(n, "parallel", False):
        style.append("dashed")
    if n.status != "todo":
        style.append("filled")
        attrs.append('fillcolor="#dcfce7"' if n.status == "done" else 'fillcolor="#fef9c3"')
    attrs.append(f"style={_dot_str(','.join(style))}")
    return f"{_dot_str(n.id)} [{', '.join(attrs)}];"


_MARK = {"done": "x", "in_progress": "~", "todo": " "}


def to_waves_text(g: AnyGraph) -> str:
    out: List[str] = []
    for i, wave in enumerate(waves(g), 1):
        out.append(f"Wave {i}:")
        for nid in wave:
            n = g.by_id[nid]
            suffix = f"  ({_count(n)})" if isinstance(n, Unit) else ""
            out.append(f"  [{_MARK[n.status]}] {n.id}  {n.title}{suffix}")
    return "\n".join(out) + "\n"


def to_ready_text(g: AnyGraph) -> str:
    return "".join(f"{nid}\t{g.by_id[nid].title}\n" for nid in ready(g))


FORMATS: Dict[str, Callable[[AnyGraph], str]] = {
    "json": to_json,
    "yaml": to_yaml,
    "mermaid": to_mermaid,
    "dot": to_dot,
    "waves": to_waves_text,
    "ready": to_ready_text,
}


def _count(u: Unit) -> str:
    n = len(u.tasks)
    done = sum(t.done for t in u.tasks)
    text = f"{n} task" + ("s" if n != 1 else "")
    return f"{text}, {done} done" if done else text


def _trunc(text: str, max_len: int) -> str:
    return text if len(text) <= max_len else text[: max_len - 1].rstrip() + "…"


def _safe_id(text: str) -> str:
    return re.sub(r"\W", "_", text)


def _mermaid_text(text: str) -> str:
    return text.replace('"', "#quot;")


def _dot_str(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'
