from pathlib import Path
from textwrap import dedent

from speckit_dag import Options, build_graph, parse_tasks

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "examples" / "specs" / "001-user-auth" / "tasks.md"
SCHEMA = ROOT / "schema" / "speckit-dag.schema.json"


def build(md: str, **opts):
    return build_graph(parse_tasks(dedent(md)), Options(**opts))


def edges(g):
    return set(g.edges)
