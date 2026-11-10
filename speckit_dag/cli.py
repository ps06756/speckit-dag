"""Command line: speckit-dag specs/001-feature/tasks.md -f mermaid"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional, Tuple

from .emit import FORMATS
from .graph import CycleError
from .parser import parse_tasks
from .rules import Options, build_graph
from .spec import locate_spec
from .units import UNITS, group_by_story


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(
        prog="speckit-dag",
        description="Build a dependency graph (DAG) from a Spec Kit tasks.md.",
    )
    p.add_argument("input", help="tasks.md, a spec folder that contains one, or - for stdin")
    p.add_argument("-f", "--format", choices=list(FORMATS), default="json", help="output format (default: json)")
    p.add_argument("-o", "--output", help="write to this file instead of stdout")
    p.add_argument(
        "--unit",
        choices=UNITS,
        default="task",
        help="what a node is: one task (default), or one story, where each phase "
        "(Setup, Foundational, each user story, Polish) is a single unit of work",
    )
    p.add_argument("--sequential-stories", action="store_true", help="run user stories one after another instead of in parallel")
    p.add_argument("--no-file-conflicts", action="store_true", help="don't order tasks that touch the same file")
    p.add_argument("--no-reduce", action="store_true", help="keep edges that longer paths already imply")
    p.add_argument("--no-git", action="store_true", help="don't record the repo, branch and commit; paths become relative to the working directory")
    p.add_argument("--strict", action="store_true", help="exit with status 1 if there are warnings")
    p.add_argument("-q", "--quiet", action="store_true", help="don't print warnings")
    args = p.parse_args(argv)

    try:
        text, source, path = _read_input(args.input)
    except OSError as e:
        print(f"speckit-dag: {e}", file=sys.stderr)
        return 1

    doc = parse_tasks(text, source)
    if path is not None:
        doc.spec = locate_spec(path, use_git=not args.no_git)
    if not doc.tasks:
        print(f"speckit-dag: no tasks found in {source}", file=sys.stderr)
        return 1

    options = Options(
        sequential_stories=args.sequential_stories,
        file_conflicts=not args.no_file_conflicts,
        reduce=not args.no_reduce,
    )
    try:
        g = build_graph(doc, options)
        if args.unit == "story":
            g = group_by_story(g, reduce=options.reduce)
        out = FORMATS[args.format](g)
    except (CycleError, RuntimeError) as e:
        print(f"speckit-dag: {e}", file=sys.stderr)
        return 1

    if args.output:
        Path(args.output).write_text(out, encoding="utf-8")
    else:
        sys.stdout.write(out)

    if not args.quiet:
        for w in g.warnings:
            print(f"warning: {w}", file=sys.stderr)
    return 1 if args.strict and g.warnings else 0


def _read_input(arg: str) -> Tuple[str, str, Optional[Path]]:
    if arg == "-":
        return sys.stdin.read(), "<stdin>", None
    path = Path(arg)
    if path.is_dir():
        path = path / "tasks.md"
    return path.read_text(encoding="utf-8"), str(path), path


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
