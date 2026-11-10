"""Find the Spec Kit feature folder around a tasks.md, and the git state it came from.

Spec Kit keeps each feature in its own folder, e.g. specs/001-user-auth/, with
spec.md, plan.md and the other design documents next to tasks.md.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Optional, Union

from .model import ParsedDoc, SpecInfo

# Spec Kit's documents, in the order /speckit.* commands create them. A trailing slash marks a folder.
SPEC_DOCS = (
    ("spec", "spec.md"),
    ("plan", "plan.md"),
    ("research", "research.md"),
    ("data-model", "data-model.md"),
    ("quickstart", "quickstart.md"),
    ("contracts", "contracts/"),
    ("checklists", "checklists/"),
)


def locate_spec(tasks_path: Union[str, Path], use_git: bool = True) -> SpecInfo:
    """Describe the feature folder that holds `tasks_path`.

    With `use_git`, paths are relative to the repository root and the repo URL,
    branch, commit, dirty and pushed flags are filled in. Without git (or outside
    a repository) paths are relative to the working directory when possible.

    `warnings` explains anything that stops a workspace cloned from the remote
    from seeing these exact files: no repository, no commit, uncommitted
    changes in the spec folder, no origin remote, or a commit not on origin.
    """
    path = Path(tasks_path).resolve()
    folder = path.parent
    root = _git(folder, "rev-parse", "--show-toplevel") if use_git else None
    base = Path(root).resolve() if root else Path.cwd().resolve()

    docs = {}
    for key, name in SPEC_DOCS:
        is_dir = name.endswith("/")
        p = folder / name.rstrip("/")
        if p.is_dir() if is_dir else p.is_file():
            docs[key] = _relative(p, base) + ("/" if is_dir else "")

    info = SpecInfo(id=folder.name, dir=_relative(folder, base), tasks=_relative(path, base), docs=docs)
    if not use_git:
        return info
    if not root:
        info.warnings.append(f"{info.tasks} isn't in a git repository, so workspaces can't fetch it")
        return info

    url = _git(folder, "remote", "get-url", "origin")
    info.repo = _strip_credentials(url) if url else None
    branch = _git(folder, "rev-parse", "--abbrev-ref", "HEAD")
    info.branch = branch if branch and branch != "HEAD" else None
    info.commit = _git(folder, "rev-parse", "--verify", "-q", "HEAD")

    # Porcelain paths are relative to the repository root.
    status = _git(folder, "status", "--porcelain", "--untracked-files=all", "--", ".", strip=False)
    if status is not None:
        info.changed = [line[3:].split(" -> ")[-1] for line in status.splitlines() if line.strip()]
        info.dirty = bool(info.changed)

    if info.commit is None:
        info.warnings.append("the repository has no commits yet, so workspaces can't fetch the spec")
    elif info.repo is None:
        info.pushed = False
        info.warnings.append("the repository has no origin remote, so workspaces can't clone it")
    else:
        on_origin = _git(folder, "branch", "-r", "--list", "origin/*", "--contains", info.commit)
        info.pushed = bool(on_origin) if on_origin is not None else None
        if info.pushed is False:
            info.warnings.append(
                f"commit {info.commit[:7]} isn't on origin yet (as of the last fetch); "
                "push it so workspaces can clone it"
            )
    if info.dirty:
        shown = ", ".join(info.changed[:5]) + (f" and {len(info.changed) - 5} more" if len(info.changed) > 5 else "")
        info.warnings.append(
            f"{info.dir} has changes that aren't committed ({shown}); "
            "workspaces cloned from the remote won't see them"
        )
    return info


def attach_spec(doc: ParsedDoc, tasks_path: Union[str, Path], use_git: bool = True) -> None:
    """Record where `doc` came from. `source` becomes the same repo-relative path as `spec.tasks`."""
    doc.spec = locate_spec(tasks_path, use_git=use_git)
    doc.source = doc.spec.tasks
    doc.warnings.extend(doc.spec.warnings)


def _relative(path: Path, base: Path) -> str:
    try:
        return path.relative_to(base).as_posix() or "."
    except ValueError:
        return path.as_posix()


def _strip_credentials(url: str) -> str:
    return re.sub(r"^(\w+://)[^@/]+@", r"\1", url)


def _git(cwd: Path, *args: str, strip: bool = True) -> Optional[str]:
    try:
        out = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    # Keep leading spaces when asked: `git status --porcelain` lines start with a status column.
    return out.stdout.strip() if strip else out.stdout.rstrip("\n")
