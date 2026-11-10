"""Graph algorithms: ordering, cycle detection, redundant-edge removal, waves.

They work on both graph types: tasks (`Graph`) and units of work (`UnitGraph`).
"""

from __future__ import annotations

import heapq
from typing import Dict, List, Optional

from .model import EdgeSet


class CycleError(ValueError):
    def __init__(self, cycle: List[str], message: Optional[str] = None):
        self.cycle = cycle
        super().__init__(message or "dependency cycle: " + " -> ".join(cycle))


def topo_order(g: EdgeSet) -> List[str]:
    """Node ids in dependency order; ties broken by position in the file."""
    succ = g.successors()
    indeg: Dict[str, int] = {n.id: 0 for n in g.nodes}
    for _, dst in g.edges:
        indeg[dst] += 1
    heap = [(g.by_id[i].order, i) for i, d in indeg.items() if d == 0]
    heapq.heapify(heap)
    out: List[str] = []
    while heap:
        _, u = heapq.heappop(heap)
        out.append(u)
        for v in succ[u]:
            indeg[v] -= 1
            if indeg[v] == 0:
                heapq.heappush(heap, (g.by_id[v].order, v))
    if len(out) < len(g.nodes):
        raise CycleError(find_cycle(g))
    return out


def find_cycle(g: EdgeSet) -> List[str]:
    """One cycle as [a, b, ..., a], or [] if the graph is acyclic."""
    succ = g.successors()
    state: Dict[str, int] = {}  # 1 = on the current path, 2 = finished
    for root in (n.id for n in g.nodes):
        if root in state:
            continue
        state[root] = 1
        path = [root]
        stack = [iter(succ[root])]
        while stack:
            nxt = next(stack[-1], None)
            if nxt is None:
                state[path.pop()] = 2
                stack.pop()
            elif state.get(nxt) == 1:
                return path[path.index(nxt) :] + [nxt]
            elif nxt not in state:
                state[nxt] = 1
                path.append(nxt)
                stack.append(iter(succ[nxt]))
    return []


def transitive_reduction(g: EdgeSet) -> None:
    """Drop edges implied by longer paths (A->B->C makes A->C redundant)."""
    order = topo_order(g)
    pos = {u: i for i, u in enumerate(order)}
    succ = g.successors()
    reach: Dict[str, int] = {}  # bitset of everything reachable from u
    for u in reversed(order):
        bits = 0
        for v in succ[u]:
            bits |= (1 << pos[v]) | reach[v]
        reach[u] = bits
    for u in order:
        indirect = 0
        for w in succ[u]:
            indirect |= reach[w]
        for v in succ[u]:
            if (indirect >> pos[v]) & 1:
                del g.edges[(u, v)]


def waves(g: EdgeSet) -> List[List[str]]:
    """Group nodes into waves: everything in a wave can run at the same time."""
    pred = g.predecessors()
    level: Dict[str, int] = {}
    for u in topo_order(g):
        level[u] = 1 + max(level[p] for p in pred[u]) if pred[u] else 0
    out: List[List[str]] = [[] for _ in range(max(level.values(), default=-1) + 1)]
    for n in g.nodes:
        out[level[n.id]].append(n.id)
    return out


def ready(g: EdgeSet) -> List[str]:
    """Nodes not yet done whose direct dependencies are all done."""
    pred = g.predecessors()
    return [
        n.id
        for n in g.nodes
        if not n.done and all(g.by_id[p].done for p in pred[n.id])
    ]
