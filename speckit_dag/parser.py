"""Parse a Spec Kit tasks.md into phases and tasks.

Recognised layout (from Spec Kit's tasks template):

    # Tasks: <feature>
    ## Phase 1: Setup
    ### Tests for User Story 1          <- optional sections inside a phase
    - [ ] T001 [P] [US1] Description in path/to/file.py (depends on T000)

Any other `##` heading that holds task lines is treated as a phase too, so
hand-written files without "Phase N:" still work. Lines inside fenced code
blocks are ignored.
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

from .model import ParsedDoc, Phase, Task

FEATURE_RE = re.compile(r"^#\s+Tasks:\s*(?P<name>.+?)\s*$")
PHASE_RE = re.compile(
    r"^##\s+Phase\s+(?P<num>[\w.]+)\s*[:\-–—]\s*(?P<name>.+?)\s*$", re.IGNORECASE
)
H2_RE = re.compile(r"^##\s+(?P<title>[^#].*?)\s*$")
H3_RE = re.compile(r"^###\s+(?P<title>[^#].*?)\s*$")
TASK_RE = re.compile(
    r"^(?P<indent>\s*)[-*+]\s+\[(?P<mark>[ xX])\]\s+(?P<id>T\d+)\b[:.]?\s*(?P<rest>.*?)\s*$"
)
TAG_RE = re.compile(r"^\[(?P<tag>[^\]]+)\]\s*")
STORY_TAG_RE = re.compile(r"US\d+", re.IGNORECASE)
STORY_RE = re.compile(r"\bUser\s+Story\s+(\d+)", re.IGNORECASE)
PRIORITY_RE = re.compile(r"\bPriority:\s*(P\d+)", re.IGNORECASE)

ID_RE = re.compile(r"\bT\d+\b")
_ID_LIST = r"T\d+(?:\s*(?:,|/|&|\band\b|\bor\b|-|–|—|\.\.|\bthrough\b|\bto\b)\s*T\d+)*"
DEP_RE = re.compile(
    r"\b(?:depends(?:\s+on)?|dependent\s+on|after|requires|blocked\s+by|needs|waits?\s+for)"
    r"\s*:?\s*(?P<ids>" + _ID_LIST + r")",
    re.IGNORECASE,
)
RANGE_JOIN_RE = re.compile(r"\s*(?:-|–|—|\.\.|through|to)\s*", re.IGNORECASE)

# File path detection
_LEAD = "`'\"([{<*"
_TRAIL = "`'\")]}>*,;:!?."
BARE_FILE_RE = re.compile(r"^[\w@+-][\w@+.-]*\.[A-Za-z][A-Za-z0-9]{0,7}$")
DOTFILE_RE = re.compile(r"^\.[A-Za-z0-9][\w.-]*$")
FRAMEWORK_RE = re.compile(r"^[A-Z][A-Za-z]*\.js$")  # Node.js, Vue.js: not files
NOT_FILES = {"e.g", "i.e", "etc"}


def parse_tasks(text: str, source: Optional[str] = None) -> ParsedDoc:
    feature: Optional[str] = None
    phases: List[Phase] = []
    tasks: List[Task] = []
    warnings: List[str] = []
    seen_ids = set()
    used_phase_ids = set()

    phase: Optional[Phase] = None
    pending_heading: Optional[str] = None  # a non-"Phase" `##` heading, becomes a phase if tasks follow
    section: Optional[str] = None
    section_index = 0
    in_fence = False
    last_task: Optional[Task] = None
    last_indent = 0

    def new_phase(name: str, number: Optional[str]) -> Phase:
        kind, story, priority, mvp = _classify(name)
        base = story or (kind if kind != "other" else _slug(name)) or f"phase-{len(phases) + 1}"
        pid, n = base, 2
        while pid in used_phase_ids:
            pid, n = f"{base}-{n}", n + 1
        used_phase_ids.add(pid)
        p = Phase(
            id=pid,
            name=f"Phase {number}: {name}" if number else name,
            kind=kind,
            index=len(phases),
            number=number,
            story=story,
            priority=priority,
            mvp=mvp,
        )
        phases.append(p)
        return p

    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.rstrip()
        stripped = line.strip()

        if stripped.startswith(("```", "~~~")):
            in_fence = not in_fence
            last_task = None
            continue
        if in_fence:
            continue

        m = FEATURE_RE.match(line)
        if m:
            feature = feature or m.group("name")
            last_task = None
            continue

        m = PHASE_RE.match(line)
        if m:
            phase = new_phase(m.group("name"), m.group("num"))
            pending_heading, section, section_index, last_task = None, None, 0, None
            continue

        m = H2_RE.match(line)
        if m:
            phase, pending_heading = None, m.group("title")
            section, section_index, last_task = None, 0, None
            continue

        m = H3_RE.match(line)
        if m:
            section, section_index, last_task = _section_key(m.group("title")), section_index + 1, None
            continue

        m = TASK_RE.match(line)
        if m:
            if phase is None:
                phase, pending_heading = new_phase(pending_heading or "Tasks", None), None
            tid = m.group("id")
            if tid in seen_ids:
                warnings.append(f"line {lineno}: duplicate task id {tid}; keeping the first one")
                last_task = None
                continue
            seen_ids.add(tid)

            rest, parallel, story, tags = _split_tags(m.group("rest"))
            if not rest:
                warnings.append(f"line {lineno}: task {tid} has no description")
            task = Task(
                id=tid,
                title=rest,
                phase=phase,
                section=section,
                section_index=section_index,
                parallel=parallel,
                story=story or phase.story,
                files=extract_files(rest),
                done=m.group("mark") in ("x", "X"),
                explicit_deps=extract_deps(rest),
                line=lineno,
                order=len(tasks),
                tags=tags,
            )
            tasks.append(task)
            last_task, last_indent = task, len(m.group("indent"))
            continue

        # Indented text under a task (a sub-bullet or wrapped line) can carry dependencies.
        indent = len(line) - len(line.lstrip())
        if last_task is not None and stripped and indent > last_indent:
            for dep in extract_deps(stripped):
                if dep not in last_task.explicit_deps:
                    last_task.explicit_deps.append(dep)
            continue
        if stripped:
            last_task = None

    return ParsedDoc(feature=feature, source=source, phases=phases, tasks=tasks, warnings=warnings)


def extract_files(text: str) -> List[str]:
    """Pull file and directory paths out of a task description."""
    files: List[str] = []
    for raw in text.split():
        tok = raw.lstrip(_LEAD).rstrip(_TRAIL)
        if not tok or "://" in tok or ID_RE.fullmatch(tok) or tok.lower() in NOT_FILES:
            continue
        if tok.startswith("./"):
            tok = tok[2:]
        if "/" in tok:
            last = tok.rstrip("/").rsplit("/", 1)[-1]
            if tok.startswith("/"):
                ok = _is_filename(last, bare=False)  # "/signup" is an endpoint, not a file
            else:
                ok = _is_filename(last, bare=False) or tok.endswith("/") or tok.count("/") >= 2
        else:
            ok = _is_filename(tok, bare=True)
        if ok and tok not in files:
            files.append(tok)
    return files


def extract_deps(text: str) -> List[str]:
    """Find task ids named as dependencies: "depends on T012", "after T010-T012"."""
    ids: List[str] = []
    for m in DEP_RE.finditer(text):
        for tid in _expand_ids(m.group("ids")):
            if tid not in ids:
                ids.append(tid)
    return ids


def _expand_ids(chunk: str) -> List[str]:
    found = list(ID_RE.finditer(chunk))
    out: List[str] = []
    i = 0
    while i < len(found):
        cur = found[i]
        if i + 1 < len(found) and RANGE_JOIN_RE.fullmatch(chunk[cur.end() : found[i + 1].start()]):
            a, b = cur.group(), found[i + 1].group()
            lo, hi, width = int(a[1:]), int(b[1:]), len(a) - 1
            if lo <= hi and hi - lo <= 1000:
                out.extend(f"T{n:0{width}d}" for n in range(lo, hi + 1))
                i += 2
                continue
        out.append(cur.group())
        i += 1
    return out


def _split_tags(rest: str) -> Tuple[str, bool, Optional[str], List[str]]:
    parallel, story, tags = False, None, []
    while True:
        m = TAG_RE.match(rest)
        if not m:
            break
        tag = m.group("tag").strip()
        rest = rest[m.end() :]
        if tag.upper() == "P":
            parallel = True
        elif STORY_TAG_RE.fullmatch(tag):
            story = tag.upper()
        else:
            tags.append(tag)
    return rest.strip(), parallel, story, tags


def _is_filename(name: str, bare: bool) -> bool:
    if DOTFILE_RE.fullmatch(name):
        return True
    if not BARE_FILE_RE.fullmatch(name):
        return False
    if bare and FRAMEWORK_RE.fullmatch(name):
        return False
    return any(c.isalpha() for c in name.rsplit(".", 1)[0])


def _classify(name: str) -> Tuple[str, Optional[str], Optional[str], bool]:
    low = name.lower()
    story = None
    sm = STORY_RE.search(name)
    if sm:
        kind, story = "story", f"US{sm.group(1)}"
    elif "setup" in low or "set up" in low:
        kind = "setup"
    elif "foundation" in low or "blocking" in low or "prerequisite" in low:
        kind = "foundational"
    elif "polish" in low or "cross-cutting" in low:
        kind = "polish"
    else:
        kind = "other"
    pm = PRIORITY_RE.search(name)
    priority = pm.group(1).upper() if pm else None
    mvp = "mvp" in low or "🎯" in name
    return kind, story, priority, mvp


def _section_key(title: str) -> Optional[str]:
    low = title.lower()
    if low.startswith("test"):
        return "tests"
    if low.startswith("implement"):
        return "implementation"
    return _slug(title) or None


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
