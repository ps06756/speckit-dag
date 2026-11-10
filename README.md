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
  "feature": "User Authentication",
  "source": "examples/tasks.md",
  "groups": [{ "id": "US1", "name": "Phase 3: User Story 1 - Sign up", "kind": "story", "order": 2,
               "story": "US1", "priority": "P1", "mvp": true }],
  "nodes":  [{ "id": "T010", "title": "Create User model in src/models/user.py", "group": "US1",
               "section": "implementation", "parallel": true, "story": "US1",
               "files": ["src/models/user.py"], "status": "todo", "line": 47, "tags": [] }],
  "edges":  [{ "from": "T010", "to": "T012", "reasons": ["sequence"] }],
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

See [`examples/`](examples) for a full input with its JSON and Mermaid output, for both tasks
(`tasks.dag.json`, `tasks.mmd`) and units (`tasks.units.json`, `tasks.units.mmd`).

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
  parser.py   tasks.md -> phases and tasks (tags, files, explicit deps)
  rules.py    one function per dependency rule, plus build_graph()
  units.py    group tasks into units of work (--unit story)
  graph.py    cycle check, redundant-edge removal, waves, ready
  emit.py     json / yaml / mermaid / dot / waves / ready
  cli.py      the speckit-dag command
schema/       JSON Schema for the generic format
examples/     sample tasks.md and its outputs
tests/
```

## Development

```bash
pip install -e '.[dev]'
pytest
```
