# Local AI Agent Enhancer

Tools, methods, and evaluations for making a small local model work reliably in
unfamiliar codebases.

This is not a finished product. It grows one project at a time: run the workflow
on a repo, watch what the agent does, and turn each failure into a countermeasure.

---

## The thesis

**Scripts measure the repo. The model only names what they find.**

Finding structure needs no understanding — it is counting connections between
files. Naming a subsystem does, and that is a small task a small model handles
well. Keeping those two jobs apart is what makes the whole thing work.

Two consequences that drive every design decision here:

- **Size is not importance.** A 402-line file that everything imports is
  critical; a 639-line file nobody imports is an entry point. Rank by dependency
  count.
- **A check the agent can reach is a check the agent can defeat.** Enforcement
  belongs in a hook, outside the model's action space.

Full reasoning: [`method/PRINCIPLES.md`](method/PRINCIPLES.md).

---

## The loop

```
   run the workflow on a project
              |
              v
   observe    projects/<name>/run-NN/     raw evidence
              |
              v
   evaluate   projects/<name>/EVALUATION.md
              |
              v
   codify     method/BEHAVIOR-REGISTRY.md  what went wrong, and why
              |
              v
   enforce    a rule (weak) | a lint check | a hook (strong)
              |
              +--------> retest, and record whether it held
```

**A behavior that recurs at rule level must be promoted to lint or hook level.**
Repeating a rule louder is not a countermeasure.

---

## Layout

```
bin/          the tools
method/       how and why — the methodology
templates/    files copied into a target repo or into Hermes
projects/     one folder per target repo: evaluations + raw evidence
history/      session records
MANUAL.md     what to run, in order
```

### `bin/` — Python tools (stdlib only, nothing to install)

| Tool | Answers | Writes |
|---|---|---|
| `repo_probe.py` | what interpreter and commands does this repo really have? | `.agent/FACTS.md` |
| `repo_graph.py` | what depends on what, and what matters? | `.agent/ARCHITECTURE.md`, `GRAPH.md` |
| `lint_agent_files.py` | are the instruction files actually usable? | exit code |
| `toolchain_scan.py` | how do my repos connect to each other? | `TOOLCHAIN.md` |
| `selftest.py` | are the tools themselves still correct? | exit code |

### `bin/` — bash tools (need Git Bash + ripgrep)

| Tool | Answers |
|---|---|
| `repo-orient.sh` | manifests, configs, entry points, license |
| `sweep.sh` | where does this vocabulary appear? |
| `verify-absence.sh` | is it all gone? — the lexical oracle |
| `agent-state.sh` | worklist and closure state, outside the model's context |

`agent-state.sh check` refuses to run without a closure oracle set. That refusal
is the point: **a task with no oracle is not agent-ready.**

### `method/`

| File | Purpose | In agent context? |
|---|---|---|
| [`PRINCIPLES.md`](method/PRINCIPLES.md) | the durable output — 21 principles, each naming the failure that produced it | no |
| [`BEHAVIOR-REGISTRY.md`](method/BEHAVIOR-REGISTRY.md) | observed agent failures across projects, each with a countermeasure | no |
| [`FRAMEWORK.md`](method/FRAMEWORK.md) | original theory | **never** |

> `FRAMEWORK.md` is ~2,500 tokens of human-facing prose. Attaching it to a
> session caused four of eight turns to fail with stream timeouts and output
> truncation. Read it once, yourself. See `BEHAVIOR-REGISTRY.md` B-007.

### `templates/`

```
repo/AGENTS.md          -> copy to a target repo root. Authoritative on process.
hermes/SKILL.md         -> auto-activating Hermes skill
hermes/guard_oracle.py  -> pre_tool_call hook: blocks evidence forgery
archive/                -> superseded versions, kept for reference
```

### `projects/`

One folder per target repo. Copy `_TEMPLATE/EVALUATION.md`, keep raw evidence in
`run-NN/`.

| Project | Role | Status |
|---|---|---|
| [`facefusion`](projects/facefusion/EVALUATION.md) | **reference fixture** — known-correct answers, catches tool regressions | not an agent target |
| [`reclip`](projects/reclip/EVALUATION.md) | agent test subject | run-01 done, run-02 prepared |

---

## Precedence

Three files can speak to the agent. When they disagree:

| File | Authoritative on | In context? |
|---|---|---|
| `AGENTS.md` (target repo root) | process, rules, behaviour | every session |
| `.agent/FACTS.md` | paths, interpreter, commands | every session |
| `.agent/ARCHITECTURE.md` | structure, what to read first | every session |
| `.agent/GRAPH.md` | full dependency table | **grepped, never pasted** |
| `method/FRAMEWORK.md` | nothing — it is for you | **never** |

---

## Quick start

```bash
python bin/repo_probe.py <repo> --deep      # interpreter + verified commands
python bin/repo_graph.py <repo>             # the dependency map
python bin/lint_agent_files.py <repo>       # gate: exit 0 = ready
cp templates/repo/AGENTS.md <repo>/AGENTS.md
```

Full walkthrough, including the debugging loop and prompt templates for the local
agent: [`MANUAL.md`](MANUAL.md).

---

## Windows

The `.sh` tools are bash — run them in **Git Bash**, not PowerShell, which
aliases `sort`, `ls`, `cat`, and `head` to cmdlets that break Unix pipelines. The
`.py` tools run anywhere.

Absolute Windows paths work in every tool, with either separator. A **leading
space inside the quotes** does not, and is invisible in the error message — all
tools now strip it and print the directory they resolved to.

---

## Known limits

- **Static analysis is ~85% of the truth.** Modules loaded by name are recovered
  when the loader has a constant prefix, and flagged when it does not. For
  certainty, merge a runtime trace — MANUAL step 4.
- **`toolchain_scan.py` proves a textual reference, not a live call.** Its output
  is leads to confirm.
- **Cohesion scores are relative.** Compare groups to each other, not to 1.0.
- **`sweep.sh` and `verify-absence.sh` only exclude `.venv`**, not `venv_311` or
  `site-packages`. Left deliberately: widening an *absence oracle's* exclusions
  is a correctness decision, and the oracle is meant to over-report.

---

## Verify before trusting

```bash
python bin/selftest.py
```

Builds a synthetic repo with a known shape, runs the tools over it, asserts every
role. Run it after editing any tool.

Every tool here has shipped with a bug that produced confident, wrong output —
including a role that could never fire and a Windows path bug that stamped every
working command as FAILED. None were caught by reading the code. That is the
normal state of generated tooling, and this is the cheapest defence.
