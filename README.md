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

See [`examples/`](examples) for a full input with its JSON and Mermaid output.

## Using it from Python

```python
from speckit_dag import load, Options, waves, ready, to_dict

g = load("specs/001-user-auth/tasks.md", Options(sequential_stories=False))
waves(g)      # [["T001"], ["T002", "T003"], ...]
ready(g)      # tasks not done whose dependencies are all done
to_dict(g)    # the generic format as a dict
```

## Layout

```
speckit_dag/
  parser.py   tasks.md -> phases and tasks (tags, files, explicit deps)
  rules.py    one function per dependency rule, plus build_graph()
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
