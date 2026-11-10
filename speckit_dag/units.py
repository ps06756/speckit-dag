"""Group tasks into units of work that can each be built and merged on their own.

A single task is often too small to merge: a story's tests fail until the code
that makes them pass lands too. With `--unit story` each phase becomes one node
(Setup, Foundational, each user story, Polish), so one node is one workspace
and one PR.
"""

from __future__ import annotations

import re
from typing import List

from .graph import CycleError, topo_order, transitive_reduction
from .model import Graph, Phase, Unit, UnitGraph

UNITS = ("task", "story")


def group_by_story(g: Graph, reduce: bool = True) -> UnitGraph:
    """One node per phase. Unit A -> unit B when any task in B depends on a task in A.

    Raises CycleError if two units end up depending on each other, which happens
    when tasks in different stories depend on each other in both directions.
    """
    pos = {tid: i for i, tid in enumerate(topo_order(g))}
    units: List[Unit] = []
    unit_of = {}
    for p in g.phases_with_tasks():
        tasks = sorted(g.tasks_in(p), key=lambda t: pos[t.id])
        unit = Unit(id=p.id, title=_title(p), phase=p, order=len(units), tasks=tasks)
        units.append(unit)
        unit_of.update((t.id, unit.id) for t in tasks)

    ug = UnitGraph(by="story", task_graph=g, nodes=units, warnings=list(g.warnings))
    for t in g.tasks:
        if t.story and t.story != t.phase.story:
            ug.warnings.append(f"{t.id} is tagged {t.story} but sits in {t.phase.id}, so it ships with {t.phase.id}")

    for (a, b), reasons in g.edges.items():
        ua, ub = unit_of[a], unit_of[b]
        if ua != ub:
            for r in reasons:
                ug.add_edge(ua, ub, r)
            ug.via.setdefault((ua, ub), []).append((a, b))
    for links in ug.via.values():
        links.sort(key=lambda k: (pos[k[0]], pos[k[1]]))

    try:
        topo_order(ug)
    except CycleError as e:
        raise CycleError(e.cycle, _explain_cycle(ug, e.cycle)) from None

    if reduce:
        transitive_reduction(ug)
        ug.via = {k: v for k, v in ug.via.items() if k in ug.edges}
    return ug


def _explain_cycle(ug: UnitGraph, cycle: List[str]) -> str:
    why = []
    for a, b in zip(cycle, cycle[1:]):
        links = ug.via[(a, b)]
        shown = ", ".join(f"{x} -> {y}" for x, y in links[:3]) + (" ..." if len(links) > 3 else "")
        why.append(f"{b} needs {a} because of {shown}")
    return (
        "grouping by story creates a cycle: " + " -> ".join(cycle) + ". "
        + "; ".join(why) + ". "
        + "Move the shared tasks into Foundational or into one story, or use --unit task."
    )


def _title(p: Phase) -> str:
    text = p.heading or p.name
    text = re.sub(r"\s*\(Priority:[^)]*\)", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*🎯", "", text)
    text = re.sub(r"\s*\bMVP\b", "", text)
    return text.strip(" -–—") or p.id
