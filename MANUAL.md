# MANUAL

What you run, in what order, on any unknown Python/JS repo.

There are two loops. **Onboarding** happens once per repo, takes about five
minutes, and is mostly automatic. **Per task** happens every time you hand work
to the local agent.

---

## Requirements

| Need | Why | Check |
|---|---|---|
| Python 3.9+ | the three `.py` tools | `python --version` |
| Git Bash | the four `.sh` scripts are bash | `bash --version` |
| ripgrep | `sweep.sh`, `verify-absence.sh` | `rg --version` |
| git | churn and coupling signals (optional) | `git --version` |

The Python tools use the **standard library only** — nothing to install. Any
Python on your PATH will do; it does not need to be the target repo's
interpreter.

---

# Loop A — Onboarding a repo (once)

## Step 1 — Find out what the machine actually is

```bash
python bin/repo_probe.py "<repo-path>" --deep
```

Writes `<repo>/.agent/FACTS.md`: the interpreter, its **real** version, and the
test/lint/typecheck commands, each stamped VERIFIED, FAILED, or UNVERIFIED.

`--deep` invokes each tool to confirm it is installed. Always use it. Without
it, everything is UNVERIFIED, which is honest but not useful.

**Read the output before continuing.** Two things to look for:

- *Is the interpreter the one you expected?* A folder named `venv_311` can hold
  any version; the tool reports what it actually answered.
- *Are the commands VERIFIED or FAILED?* FAILED means the config asks for the
  tool but it is not installed. That is normal on a fresh checkout and you fix
  it with a `pip install` — but until you do, **the repo has no oracle**, and
  nothing in it is safely delegable.

## Step 2 — Build the dependency map

```bash
python bin/repo_graph.py "<repo-path>"
```

Writes three files into `<repo>/.agent/`:

| File | Size | Use |
|---|---|---|
| `ARCHITECTURE.md` | ~40 lines | **Put this in the agent's context.** |
| `GRAPH.md` | one row per file | Leave on disk. The agent greps it. |
| `graph.json` | machine-readable | For your other tools. |

Read `ARCHITECTURE.md` yourself now. It tells you where to start reading, which
files have the largest blast radius, and which are loaded dynamically.

## Step 3 — Exclude anything dead

Most repos carry a retired subsystem. Left in, it inflates the rankings and
sends the agent to read code that no longer matters.

Create `<repo>/.agent/graph-ignore.txt`:

```
# one glob per line, '#' comments allowed
legacy/*
old-launcher/*
```

Then re-run step 2. Or pass it inline:

```bash
python bin/repo_graph.py "<repo-path>" --ignore "legacy/*"
```

## Step 4 — Close the dynamic-import gap (Python; do this if the repo runs)

Steps 2's map is complete for `import` statements and **inferred** for anything
loaded by name at runtime. To replace the inference with observation, run the
app once and record what really loaded:

```bash
<interpreter-from-FACTS.md> -X importtime <entry-point> 2> trace.txt
python bin/repo_graph.py "<repo-path>" --import-trace trace.txt
```

The entry point comes from the "Start here" section of `ARCHITECTURE.md`.

You do not need the program to do anything useful — it only has to start, import
its modules, and exit. Ctrl-C once it is up is fine.

**Skip this if the repo cannot run.** The map stays valid; its Confidence
section will say the dynamic wiring is inferred rather than observed, which is
the honest state.

## Step 5 — Have the AI name the subsystems

`ARCHITECTURE.md` has a Subsystems table with an empty column:

```
| Group                  | Files | Cohesion | AI: what is this? |
| `app/processors`       | 61    | 0.24     | _(unlabelled)_    |
```

Hand the agent **one row at a time** with the file names in that group and ask
what it is. This is the only step where the model's judgement is used, and it is
a naming task with ~20 lines of input — well within a small model's ability.

Paste its answers into the table. This is the highest-value thirty seconds in
the whole process: it turns a folder listing into a map.

## Step 6 — Install the rules

```bash
cp templates/repo/AGENTS.md "<repo-path>/AGENTS.md"
```

Then fill the two hand-written items at the top: **what the project is** (one
sentence) and its **landmines**. Everything else is already in the generated
files and must not be duplicated.

## Step 6b — Lint the setup before trusting it

```bash
python bin/lint_agent_files.py "<repo-path>"
```

Exit 0 means the agent can start. Exit 1 prints exactly what is broken. It
catches the failures nothing else reports:

- unfilled `<...>` placeholders — the model invents values for these
- a **stale map** (stamped commit is no longer HEAD)
- **no VERIFIED command** — meaning no oracle, so nothing is delegable
- a pending worklist with no closure oracle set
- **a higher-priority context file shadowing your `AGENTS.md`** (see below)
- a context file over the 20,000-char cap, whose middle gets silently dropped

Run it at the start of every session. It is cheap and it is the only check on
the instruction files themselves.

### The shadowing trap

Hermes loads **one** project context file per session, first match wins:

```
.hermes.md / HERMES.md   ->  AGENTS.md  ->  CLAUDE.md  ->  .cursorrules
```

A repo containing both `.hermes.md` and `AGENTS.md` loads **only** `.hermes.md`.
Your `AGENTS.md` is never read and nothing anywhere says so. The linter reports
this as an ERROR because it is invisible at every other layer.

## Step 7 — Ignore the working files, keep the map

Add to the repo's `.gitignore`:

```
.agent/*
!.agent/ARCHITECTURE.md
!.agent/FACTS.md
```

---

# Loop B — Per task

## Step 8 — Set the oracle before doing anything else

```bash
S=bin/agent-state.sh
$S init "<what you want done>"
$S closure "<a VERIFIED command from FACTS.md>"
```

`closure` is the command that proves the task is finished. If FACTS.md has no
VERIFIED command, **stop here** — a task with no oracle is not agent-ready, and
you own it yourself.

For a bug fix the oracle is the failing repro flipping to passing:

```bash
$S closure "<interpreter> -m pytest tests/test_thing.py::test_broken"
```

## Step 9 — Locate

```bash
printf 'guess1\nguess2\n' > .agent/terms-seed.txt
bash bin/sweep.sh .agent/terms-seed.txt <source-dirs>
head -5 .agent/sweep-ranked.txt
```

**Everything the workflow creates goes in `.agent/`, never the repo root.** An
earlier version of this manual wrote `terms-seed.txt` to the working directory,
and an agent following it faithfully littered the project root. Working files
belong where `.gitignore` already covers them.

Open those top files, extract the project's **real** identifiers, then sweep
again on those. **Round two is the one that matters** — round one only exists to
teach you the vocabulary.

## Step 10 — Queue and work

```bash
$S addf .agent/sweep-files.txt
$S next          # one unit
$S done <unit>
```

Hand the agent one unit at a time, with `AGENTS.md` and `ARCHITECTURE.md` in
context. Never paste `GRAPH.md` — let it grep.

## Step 11 — Close

```bash
$S check
```

Exit 0 only when the worklist is empty **and** the oracle passes. Anything else
is not done.

---

# Loop B2 — Debugging (a different oracle)

Loop B assumes you know what to change and need to find every instance. Debugging
is the opposite: one defect, unknown location, no worklist. Its oracles are all
absence oracles — "the sweep returns zero" — and none of them fit.

**The debugging oracle is a failing test that flips to passing.** Borrowed from
test-driven development, where it is called RED → GREEN → REFACTOR. It is a
stronger oracle than any absence check, because it proves behaviour rather than
the absence of text.

## Step D1 — Make the bug reproducible as a command

Not a description. A command with an exit code.

```bash
<interpreter-from-FACTS.md> -m pytest tests/test_thing.py::test_broken
```

If no such test exists, **write the failing test first** and confirm it fails
for the right reason. A test that passes before your fix proves nothing; a test
that errors for an unrelated reason is worse than none.

This step is not optional overhead. Until the bug is a command, there is no
oracle, and the task is not agent-ready — you are debugging by hand.

## Step D2 — RED: confirm it fails

```bash
S=bin/agent-state.sh
$S init "fix <the bug>"
$S closure "<the repro command>"
$S check        # MUST report OPEN. If it passes now, you have the wrong repro.
```

A closure oracle that is already green means you are about to "fix" something
that is not broken.

## Step D3 — Hypothesis before edit

Do not hand the agent the task yet. First make it justify where it will look,
using the map rather than a search. MANUAL Template 3 is written for this.

You are checking one thing: are its three candidates supported by the graph, or
did it guess? If it guessed, the map is not in its context and nothing that
follows will be reliable.

## Step D4 — GREEN: smallest change that flips the oracle

Hand it one unit, minimal-diff rung 1 first, with `ORACLE:` set to the repro
command. Same machinery as Loop B — only the closure command differs.

## Step D5 — REFACTOR: only once green

Clean up after the oracle passes, re-running it after each change. Never
refactor and fix in the same edit; if the oracle goes red you will not know
which one broke it.

## Why this matters more for a bug than a refactor

A refactor has a natural safety net — the build. A bug fix does not: code can
compile perfectly and still be wrong. The failing-test oracle is the only
mechanical proof that the behaviour actually changed, and without it the agent
will report success on the strength of a green build, which cannot see the bug.

---

# Loop C — Driving the local agent

The tools produce artifacts. This is how you hand them to a small local model so
it uses them instead of wandering off to explore.

## The one rule

**Never ask the model to find something. Tell it what to open.**

Exploration is the thing small models are worst at, and every artifact in
`.agent/` exists so that they never have to. A prompt that begins "look through
the codebase and..." throws away the entire pipeline.

## Prompt shape

Every order has the same four parts. Keep them in this order and keep them short.

```
CONTEXT:  which files to read (and which NOT to)
TASK:     one sentence
UNIT:     exactly one file path
ORACLE:   the command that proves you are done
```

## Template 1 — labelling a subsystem (onboarding step 5)

```
Read .agent/ARCHITECTURE.md only. Do not open any source file.

These 14 files form one group:
  <paste the file names from GRAPH.md for that group>

In ONE line: what is this subsystem?
No reasoning, no preamble.
```

Small models do this well. It is naming, not searching, and the whole input is
twenty lines.

## Template 2 — a change task

```
CONTEXT: Read AGENTS.md, .agent/FACTS.md, .agent/ARCHITECTURE.md.
         Do NOT read .agent/GRAPH.md — grep it if you need one file's dependents.

TASK:    <one sentence>
UNIT:    <one file path>
ORACLE:  <a VERIFIED command copied from FACTS.md>

Rules:
- State which minimal-diff rung you are using BEFORE you edit.
- Edit only the file named in UNIT.
- Run ORACLE after the edit and paste its exit code.
- If something is ambiguous, append it to .agent/questions.md and continue.
  Do not stop to ask.
- Finish with the report block from AGENTS.md rule 10.
```

## Template 3 — debugging (hypothesis first, no edits)

Debugging has no worklist, so it needs a different opening move: make the model
justify where it will look before it touches anything.

```
CONTEXT: Read .agent/ARCHITECTURE.md. Do not edit anything yet.

REPRO:    <command that fails>
EXPECTED: <what should happen>
ACTUAL:   <what happens>

Step 1 only: name the 3 files most likely responsible.
For each, give the reason FROM THE MAP (its role, and its in-degree).
Then stop and show me the list.
```

Once you agree with the list, issue Template 2 with `ORACLE: <the repro command>`.
A failing test that flips to passing is a real oracle — the same machinery as a
refactor, just a different closure command.

## What never to paste

| Never paste | Why | Instead |
|---|---|---|
| `GRAPH.md` | hundreds of rows, buries the signal | tell it to grep |
| `method/FRAMEWORK.md` | ~2,500 tokens of prose about the model | never — it is for you |
| Raw tool output | re-fills the window every turn | write to a file, name the path |
| More than one unit | the model batches and loses track | one file per order |

## If the model ignores the rules

Check, in this order:

1. **Is a persona overriding your rules?** A "personality" system prompt in the
   agent config silently competes with your engineering rules and usually wins —
   it is later in the prompt and more concrete. Engineering rules and a
   role-play persona cannot both be the system prompt.
2. **Is the ruleset too long?** Rules compete for attention. If the model follows
   rule 1 and ignores rule 9, move rule 9 up, or delete a rule to make room.
3. **Was the rule stated as a goal or as a prohibition?** Small models follow
   "never do X" far more reliably than "prefer Y". Name the wrong answer.
4. **Is it enforceable instead?** A rule the platform can enforce with a hook
   beats a rule the model must remember. Prompts persuade; hooks guarantee.

---

# Maintenance

## When to regenerate

`ARCHITECTURE.md` records the commit it was built from. If that is not `HEAD`,
the map is stale. Regenerate after any structural change — files added, moved,
renamed, or deleted.

Cheap check:

```bash
head -3 "<repo>/.agent/ARCHITECTURE.md"   # compare to: git rev-parse --short HEAD
```

A stale map is worse than no map, because it is confidently wrong.

## Cross-repo (when you have several)

```bash
python bin/toolchain_scan.py "<directory-containing-your-repos>"
```

Writes `TOOLCHAIN.md` beside the repos: which repo references which, and which
share a port. Run it when you add a repo, and read it first when returning to an
old one.

Note the argument is the **parent** directory, not a repo.

---

# Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `no such directory: [ path]` | leading space in the quoted argument | remove it — note the space before `path` in the message |
| Everything is `ORPHAN?` | wrong root, or source under an ignored dir | check the file count in the output |
| The Commits column is all 0 | source is not git-tracked | the map says so in Confidence; ignore churn |
| Nothing detected in step 1 | no venv, or a non-standard location | pass the interpreter path by hand in AGENTS.md |
| A subsystem you know exists is missing | it is loaded dynamically | do step 4 |
| `dynamic (inferred)` count is 0 but you expect plugins | loader uses a fully variable name | check GRAPH.md's "loads modules by name" list |

## Verifying the tools themselves

```bash
python bin/selftest.py
```

Builds a throwaway repo with a deliberately known shape, runs the tools over it,
and asserts every classification. Exit 0 means correct; exit 1 means something
regressed. Run it after editing any tool, and before trusting the output on a
repo that matters.

Every one of these tools has shipped with a bug that produced confident, wrong
output. None were caught by reading the code; all were caught by running them
against something whose answer was known in advance.
