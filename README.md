# speckit-dag

Turn a [Spec Kit](https://github.com/github/spec-kit) `tasks.md` into a dependency graph (DAG) in a
generic JSON/YAML format, plus Mermaid and Graphviz views.

```bash
pip install -e '.[yaml]'
speckit-dag specs/001-user-auth/tasks.md               # generic JSON graph
speckit-dag specs/001-user-auth -f mermaid -o dag.mmd  # a spec folder works too
speckit-dag specs/001-user-auth -f waves               # what can run in parallel
speckit-dag specs/001-user-auth -f ready               # what can start right now
```

Formats: `json` (default), `yaml`, `mermaid`, `dot`, `waves`, `ready`.
No runtime dependencies; YAML output needs PyYAML.

## Tasks or units of work

By default a node is one Spec Kit task. That is too small to build and merge on its own: a
story's test tasks (T008, T009) fail until the tasks that make them pass (T010–T013) land, so
merging T008 alone turns CI red.

`--unit story` makes each phase one node: Setup, Foundational, each user story and Polish.
One node is one workspace and one PR.

```bash
speckit-dag specs/001-user-auth --unit story -f waves
```
```
Wave 1:
  [~] setup  Setup (Shared Infrastructure)  (3 tasks, 1 done)
Wave 2:
  [ ] foundational  Foundational (Blocking Prerequisites)  (4 tasks)
Wave 3:
  [ ] US1  User Story 1 - Sign up with email  (6 tasks)
  [ ] US2  User Story 2 - Log in  (3 tasks)
Wave 4:
  [ ] US3  User Story 3 - Reset password  (2 tasks)
Wave 5:
  [ ] polish  Polish & Cross-Cutting Concerns  (3 tasks)
```

- A unit depends on another when any of its tasks depends on a task in the other. Here US3
  waits for US1 because T017 depends on T011.
- Each unit node lists its `tasks` in the order to do them, so tests come before the code
  that makes them pass. Each unit edge lists, in `via`, the task edges that cause it.
- A unit is `done` when all its tasks are, `in_progress` when some are, and `todo` otherwise.
- Grouping can create a cycle when two stories have tasks that depend on each other in both
  directions, even though the task graph is fine. The error names the tasks causing it:

  ```
  speckit-dag: grouping by story creates a cycle: US1 -> US2 -> US1. US2 needs US1 because
  of T001 -> T003; US1 needs US2 because of T004 -> T002. Move the shared tasks into
  Foundational or into one story, or use --unit task.
  ```
- A task tagged with one story but placed in another phase ships with its phase, and you get
  a warning.

## How dependencies are worked out

Spec Kit mostly implies dependencies through layout. Each rule adds edges, tagged with the
reason so you can trace any edge back to its rule:

| Reason | Rule |
|---|---|
| `explicit` | The task text names them: `depends on T012`, `after T010, T011`, `blocked by T008-T010`. Indented lines under a task count too. |
| `phase` | Setup → Foundational → user stories → Polish. Neighbouring user-story phases run **in parallel** (`--sequential-stories` to chain them). |
| `section` | `###` sections inside a phase run in order, so tests come before implementation. |
| `sequence` | A task without `[P]` waits for the tasks before it in its section. A run of `[P]` tasks all wait on the same earlier task, not on each other. |
| `file` | Tasks that touch the same file run in file order, even if both are `[P]` (`--no-file-conflicts` to turn off). Directories (`src/models/`) don't count. Warns when this links two user stories. |

The graph is then checked for cycles (the error names the cycle) and redundant edges are removed:
`A→B→C` makes `A→C` unnecessary. Use `--no-reduce` to keep them.

`--strict` exits with status 1 on warnings, such as a dependency on an unknown task.

## The generic format

Defined in [`schema/speckit-dag.schema.json`](schema/speckit-dag.schema.json). Nothing in it is
Spec Kit-specific, so other planners can produce the same file.

```json
{
  "version": 1,
  "unit": "task",
  "hash": "sha256:7a26eee8f727a162ad0fe561131d0809a1a9ced97a5e08956e5765bb38f8e24a",
  "feature": "User Authentication",
  "source": "specs/001-user-auth/tasks.md",
  "spec": {
    "id": "001-user-auth",
    "dir": "specs/001-user-auth",
    "tasks": "specs/001-user-auth/tasks.md",
    "docs": { "spec": "specs/001-user-auth/spec.md", "plan": "specs/001-user-auth/plan.md",
              "data-model": "specs/001-user-auth/data-model.md" },
    "repo": "git@github.com:acme/app.git",
    "branch": "001-user-auth",
    "commit": "c2bb496a07c292b289bf27cd3bb21cfc3c09373b",
    "dirty": false,
    "pushed": true
  },
  "groups": [{ "id": "US1", "name": "Phase 3: User Story 1 - Sign up with email (Priority: P1) 🎯 MVP",
               "kind": "story", "order": 2, "story": "US1", "priority": "P1", "mvp": true,
               "line": 36, "end_line": 53,
               "text": "## Phase 3: User Story 1 - Sign up with email ...\n\n**Goal**: A visitor can ..." }],
  "nodes":  [{ "id": "T012", "title": "Implement SignupService in src/services/signup.py",
               "group": "US1", "section": "implementation", "parallel": false, "story": "US1",
               "files": ["src/services/signup.py"], "status": "todo",
               "ref": "specs/001-user-auth/tasks.md#T012", "line": 49, "end_line": 52, "tags": [],
               "text": "- [ ] T012 [US1] Implement SignupService in src/services/signup.py\n  - Hash the password with the helpers in src/lib/crypto.py\n  - ..." }],
  "edges":  [{ "from": "T011", "to": "T012", "reasons": ["sequence"] }],
  "waves":  [["T001"], ["T002", "T003"]],
  "warnings": []
}
```

An edge means `to` depends on `from`. `waves` groups tasks that can run at the same time.
`unit` says what a node is: `task`, or `story` for units of work. Unit nodes add `kind`
and a `tasks` list, and unit edges add `via`:

```json
{ "from": "US1", "to": "US3", "reasons": ["explicit"], "via": [{ "from": "T011", "to": "T017" }] }
```

### Finding the task in the spec

- **`spec`** says where the feature lives: its folder, its `tasks.md`, the other Spec Kit
  documents found next to it, and the git repo, branch and commit the graph was built from.
  Paths, `source` included, are relative to the repository root wherever you run the command.
  Outside a repository, or with `--no-git`, they are relative to the working directory and the
  git fields are null. Input from stdin has no `spec`.
- **`ref`** on each task is `<path to tasks.md>#<task id>`. It stays valid when lines move.
  To resolve it, open the file and search for the task ID; `line` is only a hint.
- **`text`** is the task as written, including indented notes or code under it. Groups and
  unit nodes carry their whole section, so a story unit includes its Goal and Independent Test.

### Graph identity

- **`hash`** identifies the graph's content: the same tasks give the same hash on any commit,
  branch or machine. An orchestrator can assign its own DAG id and store the hash beside it.
  Importing a file with a known hash is a re-import, not a new DAG; a different hash for the
  same spec is a new version, so a running DAG is never changed underneath it.
  - It covers the groups, nodes and edges, the `unit`, and the format version.
  - It leaves out where the graph came from (`source`, `spec`, `ref`), line numbers, and
    progress (`status`, and the `[x]` marks in `text`). Ticking tasks done or adding a blank
    line keeps the hash. Changing a task, its notes, a story's Goal, a dependency, or an option
    such as `--sequential-stories` gives a new one.
- **`dirty`** is true when anything in the spec folder (modified, staged or untracked) differs
  from the commit. **`pushed`** is true when the commit is on an `origin` branch, as of the
  last fetch. Workspaces clone from the remote, so a dirty or unpushed spec points at text
  they can't see.
- Each of these gets a warning, and `--strict` fails on warnings: uncommitted changes in the
  spec folder, a commit not on `origin`, no `origin` remote, no commits, or not being in a git
  repository. Changes outside the spec folder don't count. `--no-git` skips the checks.

  ```
  warning: specs/001-user-auth has changes that aren't committed (specs/001-user-auth/tasks.md);
  workspaces cloned from the remote won't see them
  warning: commit 2fedf30 isn't on origin yet (as of the last fetch); push it so workspaces can clone it
  ```

  `pushed` is only as fresh as the last `git fetch`, so the orchestrator should still check at
  import that the commit is on the remote, and refuse the graph if it isn't.

See [`examples/specs/001-user-auth/`](examples/specs/001-user-auth) for a sample feature folder,
and [`examples/output/`](examples/output) for its JSON and Mermaid output, for both tasks
(`tasks.dag.json`, `tasks.mmd`) and units (`units.json`, `units.mmd`). The JSON there is
built with `--no-git` so it doesn't change with every commit.

## Using it from Python

```python
from speckit_dag import load, Options, group_by_story, waves, ready, to_dict

g = load("specs/001-user-auth/tasks.md", Options(sequential_stories=False))
waves(g)      # [["T001"], ["T002", "T003"], ...]
ready(g)      # tasks not done whose dependencies are all done
to_dict(g)    # the generic format as a dict

units = group_by_story(g)   # raises CycleError if stories depend on each other
ready(units)  # ["setup"]
units.by_id["US1"].tasks    # the tasks to do in that workspace, in order
```

## Layout

```
speckit_dag/
  parser.py   tasks.md -> phases and tasks (tags, files, deps, text)
  rules.py    one function per dependency rule, plus build_graph()
  units.py    group tasks into units of work (--unit story)
  spec.py     find the spec folder, its documents and the git state
  identity.py the content hash
  graph.py    cycle check, redundant-edge removal, waves, ready
  emit.py     json / yaml / mermaid / dot / waves / ready
  cli.py      the speckit-dag command
schema/       JSON Schema for the generic format
examples/     a sample Spec Kit feature folder and its outputs
tests/
```

## Development

```bash
pip install -e '.[dev]'
pytest
```
