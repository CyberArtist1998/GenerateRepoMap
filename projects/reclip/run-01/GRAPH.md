# GRAPH - full dependency table

_Commit `297b79d`. Do not read this whole file - grep it._

Roles: CORE (many importers) | ENTRY (start here) | ORCHESTRATOR (imports many) |
LEAF (isolated) | PLUGIN (loaded by name) | RUNTIME-LOADED (observed) | ORPHAN? (unreferenced)

| File | Role | In | Out | Commits | Group |
|---|---|---:|---:|---:|---|
| `install.js` | ENTRY | 0 | 0 | 1 | `(root)` |
| `pinokio.js` | ENTRY | 0 | 0 | 1 | `(root)` |
| `reset.js` | ENTRY | 0 | 0 | 1 | `(root)` |
| `start.js` | ENTRY | 0 | 0 | 1 | `(root)` |
| `update.js` | ENTRY | 0 | 0 | 1 | `(root)` |
| `app/app.py` | ENTRY | 0 | 0 | 0 | `app` |

