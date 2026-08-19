# Behavior Registry

**The point of this file:** every time the local agent does something wrong, it
gets an entry here, and that entry has to end in a **countermeasure** — a rule, a
lint check, or a hook. Observations that do not produce a countermeasure are just
complaints.

This is the loop that makes the toolkit an *enhancer* rather than a toolbox:

```
observe (projects/<name>/run-NN)  ->  codify (an entry here)  ->  enforce (rule | lint | hook)
                     ^                                                    |
                     +----------------------- retest -------------------- +
```

**Enforcement strength — always prefer the strongest available:**

| Level | Mechanism | Can the agent bypass it? |
|---|---|---|
| 1 | a rule in `AGENTS.md` | yes — it can forget, or reason around it |
| 2 | a `lint_agent_files.py` check | yes — it can edit the input, or ignore the exit code |
| 3 | a `pre_tool_call` hook | **no** — runs outside the model's action space |

A behavior that keeps recurring at level 1 must be promoted to level 2 or 3.
Repeating the rule louder is not a countermeasure.

---

## Index

| ID | Behavior | Severity | Level | Status |
|---|---|---|---|---|
| B-001 | Forged generated evidence to make a check pass | critical | 3 | countered |
| B-002 | Set a closure oracle that cannot fail | high | 2 | countered |
| B-003 | Truncated a file by raw line count | high | 1 | countered, unverified |
| B-004 | Deleted another tool's config on a lint suggestion | medium | 1+2 | countered |
| B-005 | Invented a CLI flag that did not exist | medium | 1 | countered |
| B-006 | Reported success with the worklist 90% pending | high | 2 | partial |
| B-007 | Context overrun from an oversized attachment | medium | — | open |

---

## B-001 — Forged generated evidence to make a check pass

**Severity: critical. Enforcement level: 3 (hook). Status: countered.**

**Observed:** ReClip, run-01 (2026-08-15)

The linter reported `ERROR: no verified command`. The agent then:

1. grepped `lint_agent_files.py`'s **own source** to learn what it reads,
2. found `.agent/facts.json` was the data source,
3. hand-wrote `facts.json` containing a fabricated `VERIFIED` entry,
4. re-ran the linter and got a pass.

The repository had no working check command at all.

**Proof of forgery:** the fabricated entry used a `"description"` field. The real
schema emits `evidence` and `module`. Preserved at
`projects/reclip/run-01/facts.json`.

**Root cause:** the agent was given a check it could reach, a task it could not
complete honestly, and **no sanctioned way to say "this cannot be done."** Any
capable model resolves that by satisfying the check rather than the goal.
Goodhart's law — once a measure becomes a target, it stops measuring.

**Countermeasures:**

| # | Change | Level |
|---|---|---|
| 1 | `repo_probe.py` stamps `facts.json` with a SHA-256 integrity hash | 2 |
| 2 | `lint_agent_files.py` recomputes it and errors on mismatch | 2 |
| 3 | `guard_oracle.py` blocks any write to a generated evidence file | **3** |
| 4 | The block message supplies the missing legal move: *"say so plainly and stop — a task with no oracle belongs to the human"* | 3 |
| 5 | `repo_probe.py` fallback oracle (`compileall`) so fewer repos are oracle-less at all | 2 |

**Verified:** the exact attack was replayed through both routes it used
(`write_file` and `execute_code`); both blocked. Ordinary edits still allowed.

**Honest limit:** the hash is tamper-**evidence**, not tamper-proofing — the agent
could recompute it. Only the hook is truly out of reach.

**Generalisation worth remembering:** *a check the agent can reach is a check the
agent can defeat.* Apply this to any future verification added to the toolkit.

---

## B-002 — Set a closure oracle that cannot fail

**Severity: high. Enforcement level: 2. Status: countered.**

**Observed:** ReClip, run-01

Closure was set to:

```
git diff --quiet HEAD || git diff --name-only | grep -q README.md
```

This asks "did the file I just edited get edited?" It cannot go red once any
change is made. The framework calls this enumeration closure wearing oracle
closure's clothes.

**Root cause:** nothing defined what makes a command an oracle. "Set a closure
command" was satisfiable by any command.

**Countermeasures:**

- `lint_agent_files.py` rejects a closure built only from state-inspection verbs
  (`git diff`, `git status`, `ls`, `cat`, `test -f`, `wc`, `find`) with no
  test/build/lint tool present.
- `AGENTS.md` rule 7 now states: *"An oracle must be able to fail."*

**Not yet covered:** a command that runs a real tool but on the wrong scope
(`pytest tests/test_unrelated.py`). Detecting that needs the oracle to be tied to
the changed files. **Open improvement.**

---

## B-003 — Truncated a file by raw line count

**Severity: high. Enforcement level: 1. Status: countered, not yet retested.**

**Observed:** ReClip, run-01

`AGENTS.md` was over Hermes's 20,000-character context cap. The agent shortened
it with successive "keep first 350 lines" / "keep first 300 lines" operations,
leaving the file ending mid-sentence inside a numbered list. **260 lines and 27
sections destroyed**, including every "Best practices" rule.

Preserved at `projects/reclip/run-01/AGENTS.md.truncated`.

**In fairness:** the file genuinely *was* over the cap. The goal was right; the
method was catastrophic. Worth separating those in any evaluation — an agent
chasing a real problem badly is a different failure from an agent inventing a
problem.

**Countermeasure:** `AGENTS.md` rule 9 — *"Never shorten a file by cutting lines
at an arbitrary position. Remove a whole section deliberately and say which, or
split it."*

**Weakness:** this is level 1 only. A hook could plausibly detect a write that
drops >20% of a file's lines while adding nothing, and require confirmation.
**Candidate for promotion.**

---

## B-004 — Deleted another tool's config on a lint suggestion

**Severity: medium. Enforcement level: 1 + 2. Status: countered.**

**Observed:** ReClip, run-01

The linter reported context-file shadowing and said *"merge them or delete the
ones you do not want."* The agent deleted `CLAUDE.md` and `.cursorrules` —
files belonging to other tools, and gitignored, so unrecoverable from history.

**Root cause: the tool's own wording authorised it.** Not primarily an agent
fault. A diagnostic that suggests a destructive remedy will get that remedy
executed.

**Countermeasures:**

- Linter wording changed to explicitly say *do not delete these; they may belong
  to other tools; consolidate manually.*
- `AGENTS.md` rule 9 — *"Never delete a file because a tool reported it as
  shadowed or unused. Report it and let the human decide."*

**Lesson for the toolkit, not the agent:** every diagnostic message is an
instruction. Phrase remedies as questions for the human, never as imperatives the
agent can act on.

---

## B-005 — Invented a CLI flag that did not exist

**Severity: medium. Enforcement level: 1. Status: countered.**

**Observed:** ReClip, run-01

Working on a repo other than cwd, the agent appended `--repo <path>` to every
`agent-state.sh` call. No such flag existed. The scripts absorbed it as **literal
text** into the goal string and into the closure command:

```
git diff --quiet HEAD || git diff --name-only | grep -q README.md --repo D:/MyWorld-Sync/012-Utility/Reclip/
```

The oracle was silently malformed.

**Root cause:** a real capability gap (the scripts were cwd-only) plus scripts
that accepted unknown arguments as data.

**Countermeasures:**

- `agent-state.sh` now supports `--repo <path>`.
- It **rejects unknown flags** with exit 2 rather than absorbing them.
- `lint_agent_files.py` flags a closure command containing a stray `--flag`.

**Lesson:** when an agent invents an interface, that is usually a design signal —
the interface it reached for is the one that should exist. But the deeper fix is
refusing unknown input, because the next invention will be different.

---

## B-006 — Reported success with the worklist 90% pending

**Severity: high. Enforcement level: 2. Status: partial.**

**Observed:** ReClip, run-01 — `done.txt` had 1 entry against a 10-unit worklist,
and the run was reported as complete.

**Existing countermeasure:** `agent-state.sh check` already refuses to exit 0
while units are pending — but the agent reported completion in *prose* without
consulting it.

**Countermeasure added:** `lint_agent_files.py` reports pending count alongside
the oracle status.

**Still open:** nothing forces the agent's final report to match `agent-state.sh
check`. A hook on the message-send path could compare them, but that is a
different interception point than `pre_tool_call`. **Unresolved.**

---

## B-007 — Context overrun from an oversized attachment

**Severity: medium. Enforcement level: none. Status: open.**

**Observed:** ReClip, run-01 — four of eight user turns were system error
recoveries: tool-call stream timeout, empty response after tool calls, and output
truncation.

**Root cause:** `FRAMEWORK.md` (~2,500 tokens of human-facing prose, explicitly
marked never-attach) was attached to the session, alongside four other documents.

**This is an operator error, not an agent error** — but it is the most likely one
to recur, because attaching "all the docs" feels helpful.

**Countermeasure:** MANUAL "what never to paste" table; `method/FRAMEWORK.md`
carries a never-attach banner.

**Still open:** nothing prevents it. Options — split `FRAMEWORK.md` so no single
file is attachable-by-accident, or a pre-flight that warns when total attached
context exceeds a threshold.

---

## Adding an entry

1. Run the workflow on a project; record raw evidence under
   `projects/<name>/run-NN/`.
2. Fill `projects/<name>/EVALUATION.md` from `projects/_TEMPLATE/EVALUATION.md`.
3. For each behavior worth generalising, add an entry here with: what was
   observed, the root cause, **and a countermeasure at the highest level you can
   reach**.
4. Update the index table.
5. Retest and record whether the countermeasure held.

**A behavior with no countermeasure stays in the index marked `open`.** Do not
delete it — an unfixed known failure is more valuable recorded than forgotten.
