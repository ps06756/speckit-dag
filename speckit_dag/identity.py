"""A content hash that identifies a graph independently of where it was built.

The same tasks give the same hash on any commit, branch or machine, so an
orchestrator can tell a re-import of the same graph from a new version.

Covered: the format version, `unit`, groups, nodes and edges.
Left out, because they change without the work changing:
  - where the graph came from: `source`, `spec` (repo, branch, commit, paths), each task's `ref`;
  - positions in the file: `line`, `end_line`;
  - progress: `status`, and the [x] / [ ] marks inside `text`;
  - values derived from the rest: `waves`, `warnings`, `feature`.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict

_LEFT_OUT = {"ref", "line", "end_line", "status"}
_CHECKBOX_RE = re.compile(r"^(\s*[-*+]\s+)\[[xX]\]", re.MULTILINE)


def content_hash(graph: Dict[str, Any]) -> str:
    """sha256 of the canonical JSON of the covered fields of a `to_dict` result."""
    payload = {
        "version": graph["version"],
        "unit": graph["unit"],
        "groups": [_strip(g) for g in graph["groups"]],
        "nodes": [_strip(n) for n in graph["nodes"]],
        "edges": graph["edges"],
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _strip(item: Dict[str, Any]) -> Dict[str, Any]:
    out = {k: v for k, v in item.items() if k not in _LEFT_OUT}
    if isinstance(out.get("text"), str):
        out["text"] = _CHECKBOX_RE.sub(r"\1[ ]", out["text"])
    if "tasks" in out:
        out["tasks"] = [_strip(t) for t in out["tasks"]]
    return out
