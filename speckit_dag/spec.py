"""Find the Spec Kit feature folder around a tasks.md, and the git state it came from.

Spec Kit keeps each feature in its own folder, e.g. specs/001-user-auth/, with
spec.md, plan.md and the other design documents next to tasks.md.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Optional, Union

from .model import SpecInfo

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
    branch, commit and dirty flag are filled in. Without git (or outside a
    repository) paths are relative to the working directory when possible.
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
    if root:
        url = _git(folder, "remote", "get-url", "origin")
        info.repo = _strip_credentials(url) if url else None
        branch = _git(folder, "rev-parse", "--abbrev-ref", "HEAD")
        info.branch = branch if branch and branch != "HEAD" else None
        info.commit = _git(folder, "rev-parse", "HEAD")
        status = _git(folder, "status", "--porcelain", "--", str(path))
        info.dirty = bool(status) if status is not None else None
    return info


def _relative(path: Path, base: Path) -> str:
    try:
        return path.relative_to(base).as_posix() or "."
    except ValueError:
        return path.as_posix()


def _strip_credentials(url: str) -> str:
    return re.sub(r"^(\w+://)[^@/]+@", r"\1", url)


def _git(cwd: Path, *args: str) -> Optional[str]:
    try:
        out = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 else None
