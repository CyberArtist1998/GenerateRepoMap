# Evaluation — FaceFusion

**Repo path:** `D:\MyWorld-Sync\011-AI\FaceFusion`
**Language / stack:** Python 3.11 (dual-stack — a retired Pinokio JS launcher wraps the Python app)
**First mapped:** 2026-08-15

**Role in this project:** FaceFusion is the **reference fixture**. It is not an
agent test subject — it is the repo whose correct answer is known, used to catch
bugs in the tools themselves. Every tool bug found so far was caught here or on
the synthetic fixture, none by reading code.

---

## 1. Setup snapshot

| Field | Value | Source |
|---|---|---|
| Interpreter | `venv_311/Scripts/python.exe` 3.11.9 **VERIFIED** | `.agent/FACTS.md` |
| Oracle | none — 4 detected, **all FAILED** | `.agent/FACTS.md` |
| Oracle strength | n/a | — |
| Mappable files | **228** | `.agent/graph.json` |
| Dependencies | **1330** (1271 static, 59 dynamic, 0 runtime) | `.agent/graph.json` |
| Dynamic loaders | 4 files, **26 plugins recovered** | `.agent/ARCHITECTURE.md` |
| Git coverage | **3%** (7 of 228 tracked) → churn column unusable | `.agent/ARCHITECTURE.md` |
| Lint verdict | EXIT 1 — no verified command | `lint_agent_files.py` |

**Is this project a good test of the map?**

**Yes — the best available.** Rich dependency structure, a real plugin registry,
a dual-stack layout, and a nested virtualenv. It exercises nearly every code path
in `repo_graph.py`.

**Why it has no oracle:** `mypy.ini`, `.flake8`, `tests/`, and `eslint.config.cjs`
are all present, so the tools correctly detect four commands — but none of the
tools are **installed** in `venv_311`. Configured ≠ installed. This is exactly
the distinction `--deep` verification exists to expose, and it is working as
intended.

---

## 2. Known-correct answers (regression baseline)

Use these to detect tool regressions. If a run disagrees, a tool broke.

| Assertion | Expected |
|---|---|
| Top CORE file | `facefusion/types.py`, **103** importers |
| `facefusion.py` (root launcher script) | must **not** outrank the package |
| Processor modules under `processors/modules/*` | role `PLUGIN`, **26** of them |
| Files loading modules by name | **4** |
| `venv_311/` | excluded entirely from the map |
| Largest-files section | must show **filenames**, never rows of `total` |
| Churn column | must be reported as unusable, not as zeros |

---

## 3. Landmines

- **The 12 processors are loaded by string name**, not by import:
  `importlib.import_module('facefusion.processors.modules.' + processor + '.core')`.
  A reference search finds nothing. They are not dead code.
- Same pattern for UI layouts, locales, and inference backends.
- `venv_311/` is 8,477 files / 3.4M lines. Never let it into any scan.
- Only 3% of the repo is git-tracked; history-based techniques are unavailable.
- The root `*.js` files are a retired Pinokio launcher.

---

## Tool bugs caught here

Recorded because each one would have shipped silently.

| Bug | How it presented | Fix |
|---|---|---|
| `venv_311` counted as the largest source root | 8,477 files / 3.4M lines dominating the table | widened exclusions |
| "Largest source files" printed 15 rows of `total` | `xargs` batching produced 56 `total` lines; `sed 2,16p` sliced only those | filter totals explicitly |
| Entry points empty | patterns missed project-named entries (`facefusion.py`, `FF.py`) | root-script listing + `package.json` main/bin |
| `PLUGIN` role could never fire | the inferred edge itself raised in-degree | track **static** in-degree separately |
| `facefusion.py` absorbed 97 imports | a module beat a same-named package in the index | two-pass index; packages win |
| Unresolvable dynamic loaders unreported | the blindest files were the ones not flagged | track loader presence separately |
| Misfits reported 43 rows | parent-directory dependence is normal layering | flag only unrelated-peer pulls → 1 row |
| Tests and `__init__.py` in the orphan list | trained the reader to ignore the signal | distinct `TEST`/`PACKAGE` roles |
| Churn column silently all zeros | reads as "never changed" | report git coverage |
| Linter counted the interpreter's VERIFIED as a command | **claimed an oracle in a repo with none** | read structured `facts.json` |

---

## Runs

**None.** No agent has been run against FaceFusion. It is deliberately reserved
as the fixture — running an agent here would modify the baseline.

If you do want to test on it, **copy it first** and evaluate the copy.

---

## Open

- [ ] Install `pytest` / `mypy` / `flake8` into `venv_311` to give it a real
      oracle. Until then the linter correctly refuses it.
- [ ] Capture a runtime trace (`-X importtime`) to convert the 59 `dynamic` edges
      into `runtime` ground truth. This is the one repo where that would
      meaningfully validate the plugin-recovery logic.
