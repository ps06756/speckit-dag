"""Data types for parsed tasks and the dependency graphs built from them."""

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

EdgeKey = Tuple[str, str]


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
    heading: Optional[str] = None  # the heading text without "Phase N:"
    line: Optional[int] = None
    end_line: Optional[int] = None
    text: str = ""  # the whole section as written, heading included


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
    text: str = ""  # the task as written: its line plus any indented lines under it
    end_line: int = 0

    @property
    def status(self) -> str:
        return "done" if self.done else "todo"


@dataclass
class SpecInfo:
    """Where a tasks.md lives: its Spec Kit feature folder and the git state it came from.

    Paths are relative to the git repository root, or to the working directory
    outside a repository.
    """

    id: str  # the feature folder name, e.g. "001-user-auth"
    dir: str
    tasks: str
    docs: Dict[str, str] = field(default_factory=dict)  # other Spec Kit files found next to tasks.md
    repo: Optional[str] = None
    branch: Optional[str] = None
    commit: Optional[str] = None
    dirty: Optional[bool] = None  # tasks.md differs from that commit

    def ref(self, task_id: str) -> str:
        return f"{self.tasks}#{task_id}"


@dataclass
class ParsedDoc:
    feature: Optional[str]
    source: Optional[str]
    phases: List[Phase]
    tasks: List[Task]
    warnings: List[str] = field(default_factory=list)
    spec: Optional[SpecInfo] = None


class EdgeSet:
    """Edge helpers shared by both graph types.

    Subclasses provide `nodes` (items with `.id` and `.order`), `edges` and `by_id`.
    """

    nodes: list
    edges: Dict[EdgeKey, Set[str]]
    by_id: dict

    def add_edge(self, src: str, dst: str, reason: str) -> None:
        self.edges.setdefault((src, dst), set()).add(reason)

    def successors(self) -> Dict[str, List[str]]:
        out: Dict[str, List[str]] = {n.id: [] for n in self.nodes}
        for src, dst in self.edges:
            out[src].append(dst)
        for ids in out.values():
            ids.sort(key=lambda i: self.by_id[i].order)
        return out

    def predecessors(self) -> Dict[str, List[str]]:
        out: Dict[str, List[str]] = {n.id: [] for n in self.nodes}
        for src, dst in self.edges:
            out[dst].append(src)
        for ids in out.values():
            ids.sort(key=lambda i: self.by_id[i].order)
        return out

    def sorted_edges(self) -> List[Tuple[str, str, List[str]]]:
        order = {n.id: n.order for n in self.nodes}
        keys = sorted(self.edges, key=lambda k: (order[k[0]], order[k[1]]))
        return [(a, b, [r for r in REASONS if r in self.edges[(a, b)]]) for a, b in keys]


@dataclass
class Graph(EdgeSet):
    """One node per Spec Kit task."""

    feature: Optional[str]
    source: Optional[str]
    phases: List[Phase]
    tasks: List[Task]
    edges: Dict[EdgeKey, Set[str]] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    spec: Optional[SpecInfo] = None

    def __post_init__(self) -> None:
        self.by_id: Dict[str, Task] = {t.id: t for t in self.tasks}

    @property
    def nodes(self) -> List[Task]:
        return self.tasks

    def phases_with_tasks(self) -> List[Phase]:
        used = {id(t.phase) for t in self.tasks}
        return [p for p in self.phases if id(p) in used]

    def tasks_in(self, phase: Phase) -> List[Task]:
        return [t for t in self.tasks if t.phase is phase]


@dataclass
class Unit:
    """A group of tasks that ships together: one workspace, one PR."""

    id: str
    title: str
    phase: Phase
    order: int
    tasks: List[Task]  # in the order to do them

    @property
    def kind(self) -> str:
        return self.phase.kind

    @property
    def done(self) -> bool:
        return all(t.done for t in self.tasks)

    @property
    def status(self) -> str:
        if self.done:
            return "done"
        return "in_progress" if any(t.done for t in self.tasks) else "todo"

    @property
    def files(self) -> List[str]:
        out: List[str] = []
        for t in self.tasks:
            out.extend(f for f in t.files if f not in out)
        return out


@dataclass
class UnitGraph(EdgeSet):
    """One node per unit of work. Edges come from the task edges between units."""

    by: str
    task_graph: Graph
    nodes: List[Unit]
    edges: Dict[EdgeKey, Set[str]] = field(default_factory=dict)
    via: Dict[EdgeKey, List[EdgeKey]] = field(default_factory=dict)  # unit edge -> task edges behind it
    warnings: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.by_id: Dict[str, Unit] = {u.id: u for u in self.nodes}

    @property
    def feature(self) -> Optional[str]:
        return self.task_graph.feature

    @property
    def source(self) -> Optional[str]:
        return self.task_graph.source

    @property
    def spec(self) -> Optional[SpecInfo]:
        return self.task_graph.spec
