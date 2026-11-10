"""Output formats: the generic JSON/YAML graph, Mermaid, Graphviz DOT, and text views."""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Dict, List

from .graph import ready, waves
from .model import Graph, Task

FORMAT_VERSION = 1


def to_dict(g: Graph) -> Dict[str, Any]:
    """The generic graph format (see schema/speckit-dag.schema.json)."""
    return {
        "version": FORMAT_VERSION,
        "feature": g.feature,
        "source": g.source,
        "groups": [
            {
                "id": p.id,
                "name": p.name,
                "kind": p.kind,
                "order": p.index,
                "story": p.story,
                "priority": p.priority,
                "mvp": p.mvp,
            }
            for p in g.phases_with_tasks()
        ],
        "nodes": [
            {
                "id": t.id,
                "title": t.title,
                "group": t.phase.id,
                "section": t.section,
                "parallel": t.parallel,
                "story": t.story,
                "files": t.files,
                "status": t.status,
                "line": t.line,
                "tags": t.tags,
            }
            for t in g.tasks
        ],
        "edges": [{"from": a, "to": b, "reasons": r} for a, b, r in g.sorted_edges()],
        "waves": waves(g),
        "warnings": g.warnings,
    }


def to_json(g: Graph) -> str:
    return json.dumps(to_dict(g), indent=2, ensure_ascii=False) + "\n"


def to_yaml(g: Graph) -> str:
    try:
        import yaml
    except ImportError as e:  # pragma: no cover - depends on the environment
        raise RuntimeError("YAML output needs PyYAML: pip install 'speckit-dag[yaml]'") from e
    return yaml.safe_dump(to_dict(g), sort_keys=False, allow_unicode=True)


def to_mermaid(g: Graph, max_label: int = 60) -> str:
    lines = ["flowchart TD"]
    for p in g.phases_with_tasks():
        lines.append(f'  subgraph g_{_safe_id(p.id)}["{_mermaid_text(p.name)}"]')
        for t in g.tasks_in(p):
            lines.append(f'    {t.id}["{_mermaid_text(_label(t, max_label))}"]')
        lines.append("  end")
    for a, b, reasons in g.sorted_edges():
        arrow = "-.->" if reasons == ["explicit"] else "-->"
        lines.append(f"  {a} {arrow} {b}")

    lines.append("  classDef done fill:#dcfce7,stroke:#16a34a,color:#14532d")
    lines.append("  classDef parallel stroke-dasharray:4 3")
    done = [t.id for t in g.tasks if t.done]
    parallel = [t.id for t in g.tasks if t.parallel]
    if done:
        lines.append(f"  class {','.join(done)} done")
    if parallel:
        lines.append(f"  class {','.join(parallel)} parallel")
    return "\n".join(lines) + "\n"


def to_dot(g: Graph, max_label: int = 60) -> str:
    lines = [
        f"digraph {_dot_str(g.feature or 'tasks')} {{",
        "  rankdir=TB;",
        '  node [shape=box, style=rounded, fontname="Helvetica", fontsize=10];',
        "  edge [color=\"#64748b\"];",
    ]
    for p in g.phases_with_tasks():
        lines.append(f"  subgraph {_dot_str('cluster_' + p.id)} {{")
        lines.append(f"    label={_dot_str(p.name)}; style=rounded; color=\"#cbd5e1\";")
        for t in g.tasks_in(p):
            style = ["rounded"]
            attrs = [f"label={_dot_str(t.id + chr(10) + _label(t, max_label, with_id=False))}"]
            if t.parallel:
                style.append("dashed")
            if t.done:
                style.append("filled")
                attrs.append('fillcolor="#dcfce7"')
            attrs.append(f"style={_dot_str(','.join(style))}")
            lines.append(f"    {_dot_str(t.id)} [{', '.join(attrs)}];")
        lines.append("  }")
    for a, b, reasons in g.sorted_edges():
        extra = ", style=dashed" if reasons == ["explicit"] else ""
        lines.append(f"  {_dot_str(a)} -> {_dot_str(b)} [tooltip={_dot_str(','.join(reasons))}{extra}];")
    lines.append("}")
    return "\n".join(lines) + "\n"


def to_waves_text(g: Graph) -> str:
    out: List[str] = []
    for i, wave in enumerate(waves(g), 1):
        out.append(f"Wave {i}:")
        for tid in wave:
            t = g.by_id[tid]
            out.append(f"  [{'x' if t.done else ' '}] {t.id}  {t.title}")
    return "\n".join(out) + "\n"


def to_ready_text(g: Graph) -> str:
    return "".join(f"{tid}\t{g.by_id[tid].title}\n" for tid in ready(g))


FORMATS: Dict[str, Callable[[Graph], str]] = {
    "json": to_json,
    "yaml": to_yaml,
    "mermaid": to_mermaid,
    "dot": to_dot,
    "waves": to_waves_text,
    "ready": to_ready_text,
}


def _label(t: Task, max_len: int, with_id: bool = True) -> str:
    title = t.title if len(t.title) <= max_len else t.title[: max_len - 1].rstrip() + "…"
    return f"{t.id} {title}" if with_id else title


def _safe_id(text: str) -> str:
    return re.sub(r"\W", "_", text)


def _mermaid_text(text: str) -> str:
    return text.replace('"', "#quot;")


def _dot_str(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'
