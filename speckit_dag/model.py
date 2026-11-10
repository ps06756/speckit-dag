"""Data types for parsed tasks and the dependency graph."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

# Why an edge exists. Listed in this order in output.
#   explicit  - the task text says so ("depends on T012")
#   phase     - Setup -> Foundational -> user stories -> Polish
#   section   - an earlier `###` section in the same phase (e.g. tests before implementation)
#   sequence  - a task without [P] waits for the tasks before it in its section
#   file      - two tasks touch the same file
REASONS = ("explicit", "phase", "section", "sequence", "file")

PHASE_KINDS = ("setup", "foundational", "story", "polish", "other")


@dataclass
class Phase:
    """A `## Phase N: ...` block, or any `##` heading that holds tasks."""

    id: str
    name: str
    kind: str
    index: int
    number: Optional[str] = None
    story: Optional[str] = None
    priority: Optional[str] = None
    mvp: bool = False


@dataclass
class Task:
    id: str
    title: str
    phase: Phase
    section: Optional[str]
    section_index: int
    parallel: bool
    story: Optional[str]
    files: List[str]
    done: bool
    explicit_deps: List[str]
    line: int
    order: int
    tags: List[str] = field(default_factory=list)

    @property
    def status(self) -> str:
        return "done" if self.done else "todo"


@dataclass
class ParsedDoc:
    feature: Optional[str]
    source: Optional[str]
    phases: List[Phase]
    tasks: List[Task]
    warnings: List[str] = field(default_factory=list)


EdgeKey = Tuple[str, str]


@dataclass
class Graph:
    feature: Optional[str]
    source: Optional[str]
    phases: List[Phase]
    tasks: List[Task]
    edges: Dict[EdgeKey, Set[str]] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.by_id: Dict[str, Task] = {t.id: t for t in self.tasks}

    def add_edge(self, src: str, dst: str, reason: str) -> None:
        self.edges.setdefault((src, dst), set()).add(reason)

    def successors(self) -> Dict[str, List[str]]:
        out: Dict[str, List[str]] = {t.id: [] for t in self.tasks}
        for src, dst in self.edges:
            out[src].append(dst)
        for ids in out.values():
            ids.sort(key=lambda i: self.by_id[i].order)
        return out

    def predecessors(self) -> Dict[str, List[str]]:
        out: Dict[str, List[str]] = {t.id: [] for t in self.tasks}
        for src, dst in self.edges:
            out[dst].append(src)
        for ids in out.values():
            ids.sort(key=lambda i: self.by_id[i].order)
        return out

    def sorted_edges(self) -> List[Tuple[str, str, List[str]]]:
        order = {t.id: t.order for t in self.tasks}
        keys = sorted(self.edges, key=lambda k: (order[k[0]], order[k[1]]))
        return [(a, b, [r for r in REASONS if r in self.edges[(a, b)]]) for a, b in keys]

    def phases_with_tasks(self) -> List[Phase]:
        used = {id(t.phase) for t in self.tasks}
        return [p for p in self.phases if id(p) in used]

    def tasks_in(self, phase: Phase) -> List[Task]:
        return [t for t in self.tasks if t.phase is phase]
