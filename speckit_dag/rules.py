"""Rules that turn an ordered task list into dependency edges.

Spec Kit implies most dependencies through layout rather than stating them.
Each rule below adds edges for one convention; `build_graph` runs them all.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List

from .graph import topo_order, transitive_reduction
from .model import Graph, ParsedDoc, Phase, Task


@dataclass
class Options:
    # Run user stories one after another (in file order) instead of in parallel.
    sequential_stories: bool = False
    # Order tasks that touch the same file, even when both are marked [P].
    file_conflicts: bool = True
    # Remove edges already implied by longer paths.
    reduce: bool = True


def build_graph(doc: ParsedDoc, options: Options = None) -> Graph:
    """Build and validate the DAG. Raises CycleError if the rules produce a cycle."""
    options = options or Options()
    g = Graph(
        feature=doc.feature,
        source=doc.source,
        phases=doc.phases,
        tasks=doc.tasks,
        warnings=list(doc.warnings),
        spec=doc.spec,
    )
    # Phase edges come last: they link the first and last tasks of each phase,
    # which depend on the edges inside the phase.
    add_sequence_edges(g)
    add_explicit_edges(g)
    if options.file_conflicts:
        add_file_edges(g)
    add_phase_edges(g, options.sequential_stories)

    topo_order(g)  # raises CycleError
    if options.reduce:
        transitive_reduction(g)
    return g


def add_sequence_edges(g: Graph) -> None:
    """Within a phase:

    - a task without [P] waits for everything before it in its section;
    - a run of [P] tasks all wait on the same earlier task, not on each other;
    - the first tasks of a `###` section wait for the end of the previous section.
    """
    for phase in g.phases:
        before: List[Task] = []    # what the current [P] run waits on
        frontier: List[Task] = []  # tasks with nothing after them yet
        in_run = False
        current_section = None
        for t in g.tasks_in(phase):
            if t.section_index != current_section:
                current_section = t.section_index
                before, in_run = list(frontier), False
            if t.parallel:
                for s in before:
                    _link(g, s, t)
                if not in_run:
                    frontier, in_run = [], True
                frontier.append(t)
            else:
                for s in frontier:
                    _link(g, s, t)
                before, frontier, in_run = [t], [t], False


def add_explicit_edges(g: Graph) -> None:
    """Dependencies written in the task text, like "(depends on T012)"."""
    for t in g.tasks:
        for dep in t.explicit_deps:
            if dep == t.id:
                g.warnings.append(f"{t.id} lists itself as a dependency; ignored")
            elif dep not in g.by_id:
                g.warnings.append(f"{t.id} depends on unknown task {dep}; ignored")
            else:
                g.add_edge(dep, t.id, "explicit")


def add_file_edges(g: Graph) -> None:
    """Tasks that touch the same file run in file order."""
    by_file: Dict[str, List[Task]] = defaultdict(list)
    for t in g.tasks:
        for f in t.files:
            if not f.endswith("/"):  # directories are too coarse to conflict on
                by_file[f].append(t)
    for path, ts in by_file.items():
        for a, b in zip(ts, ts[1:]):
            g.add_edge(a.id, b.id, "file")
            if a.phase is not b.phase and a.phase.kind == "story" and b.phase.kind == "story":
                g.warnings.append(
                    f"{a.phase.id} and {b.phase.id} both touch {path}; ordered {a.id} -> {b.id}, "
                    "so these stories can't run fully in parallel"
                )


def add_phase_edges(g: Graph, sequential_stories: bool = False) -> None:
    """Setup -> Foundational -> user stories -> Polish.

    Neighbouring user-story phases form one tier and run in parallel, unless
    `sequential_stories` is set. Every other phase is its own tier.
    """
    tiers: List[List[Phase]] = []
    for p in g.phases_with_tasks():
        if p.kind == "story" and not sequential_stories and tiers and tiers[-1][0].kind == "story":
            tiers[-1].append(p)
        else:
            tiers.append([p])

    has_pred, has_succ = set(), set()
    for src, dst in g.edges:
        if g.by_id[src].phase is g.by_id[dst].phase:
            has_succ.add(src)
            has_pred.add(dst)

    for prev, nxt in zip(tiers, tiers[1:]):
        ends = [t for p in prev for t in g.tasks_in(p) if t.id not in has_succ]
        starts = [t for p in nxt for t in g.tasks_in(p) if t.id not in has_pred]
        for a in ends:
            for b in starts:
                g.add_edge(a.id, b.id, "phase")


def _link(g: Graph, src: Task, dst: Task) -> None:
    g.add_edge(src.id, dst.id, "section" if src.section_index != dst.section_index else "sequence")
