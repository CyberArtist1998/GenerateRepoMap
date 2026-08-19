# Project Log — Local Agent Repo Toolkit

Complete record of the 2026-08-15/16 working session: what was found, what was
decided and why, what was built, and what remains open.

> **Partly superseded.** This file was written mid-session and its §14 open items
> are out of date. For current state — including the ReClip test results, the
> three later tool bugs, and the prepared test #2 setup — read
> [SESSION-HANDOFF.md](SESSION-HANDOFF.md) instead. That file is self-contained
> and is the one to attach when resuming in a new session.
>
> This log is kept for its narrative of how each decision was reached.

---

## 1. The one-line summary

**Scripts measure the repo. The model only names what they find.**

Finding structure needs no understanding — it is counting connections between
files. Naming a subsystem does need understanding, and that is a small task a
small model handles well. Keeping those two jobs apart is what makes the whole
thing work, and it is what broke the circular problem ("to point the AI at the
right file I must already know the structure").

Three corollaries, each of which changed a concrete design decision:

1. **Size is not importance.** Rank by dependency count, not line count.
2. **Facts about a machine are generated, never typed.** Every hand-written path
   and version eventually goes stale silently.
3. **A check the agent can reach is a check the agent can defeat.** Enforcement
   must live outside the model's action space.

---

## 2. How it started — debugging `repo-orient.sh`

The reported command:

```bash
./repo-orient.sh " D:\MyWorld-Sync\011-AI\FaceFusion"
```

**Immediate cause: a leading space inside the quotes.** Not the backslashes.
Tested all four forms — Git Bash `cd` accepts `D:\repo`, `D:/repo`, and
`D:\\repo` equally. The README's claim that absolute Windows paths break
`repo-orient.sh` was wrong (it is true for `sweep.sh` / `verify-absence.sh`,
which emit `file:line`) and sent the search in the wrong direction.

Fixing the path revealed four real bugs in the script:

| # | Bug | Root cause | Fix |
|---|---|---|---|
| 1 | `venv_311` counted as largest "source root" (8,477 files / 3.4M lines) | `EXCLUDE` had `.venv` but not `venv*` or `site-packages` | widened, segment-anchored |
| 2 | "Largest source files" printed 15 rows of `total` and no filenames | 8,477 paths exceed `xargs` limit → **56 batches → 56 `total` lines**; `sort -rn` floats them to the top; `sed -n '2,16p'` sliced only totals | filter totals explicitly, `head -15` |
| 3 | "Entry point candidates" empty | conventions only matched `main.*`/`index.js`; the repo's entries were named after the project | added root-level script listing + `package.json` main/bin |
| 4 | Config section missed `.ini` files | no `*.ini`/`*.cfg` patterns | added |

Also made the source-roots loop single-pass (it walked each subtree twice).
Runtime **13.2s → 3.5s**.

Bug 2 is the instructive one: `sed -n '2,16p'` only ever worked because the
author assumed exactly one trailing `total` line. It was correct on small repos
and silently useless on large ones.

---

## 3. Evaluation of the original framework

### What was right

- **The core thesis** — *"the binding constraint is not the model's
  intelligence, it is verifiability."* Correct and non-obvious. Most local-agent
  scaffolding tries to fix small-model weakness with more context or RAG; this
  fixes it with oracles and external state.
- **§7's three-tier stopping criteria** (loop detection / enumeration closure /
  oracle closure) with explicit strength ratings. Naming the weak ones as weak
  is what makes it useful.
- **§5 minimal-diff ladder.** Highest-leverage idea in the document. Turning a
  40-call-site edit into one `return true` doesn't just reduce risk — with an
  output cap it is the difference between "possible" and "corrupts the file".
- **`agent-state.sh check` refusing to run without an oracle.** Discipline that
  is mechanically enforced rather than advisory.

### What was wrong

**It is a refactor framework, not a debugging framework.** All three of §7's
constructible oracles are *absence* oracles. The pipeline is
sweep → worklist → edit → verify-absence, which is search-and-destroy over a
known enumeration. Debugging has no worklist, one defect at an unknown location,
and needs hypothesis → experiment → revise. By the framework's own §11, that is
work assigned to a human or frontier model.

**It names its own biggest gap and doesn't tool it.** §1 rates layer 6 (dynamic
— run it, trace it) as "most under-used and highest-value". All four original
scripts are layers 1–2. No tracing helper existed.

**§11 quietly concedes the headline.** Of eight work types, four are "you or
frontier model", one is "script", three go to the local agent. The closing line:
*the local model is a competent editor and a poor explorer.* That is the real
architecture and it was buried in the last table.

---

## 4. Review of the three instruction files

Three verified defects, all confirmed against the machine:

1. **`Agent.md` deadlocked on turn one.** It declared six required files and
   said *"stop the task completely if any of it is messing."* Five did not
   exist — because they are **outputs** of the pipeline, not preconditions.
2. **Every concrete path was wrong.** It claimed a "Python 3.14 venv at `venv/`".
   Reality: `venv_311/`, Python **3.11.9**. Root cause found later — the system
   Python *is* 3.14.6, so someone read the system interpreter's version and
   wrote it down as the project's. The file's own section was titled
   *"Verify before you claim"*.
3. **No file named an oracle**, though the repo shipped `mypy.ini`, `.flake8`,
   `tests/`, and `eslint.config.cjs`.

Plus a structural problem: **redundancy without a precedence rule.** The same
rules appeared in two or three files with different wording, and where they
diverged the model had no tiebreaker.

**Decision — the precedence rule:**

| File | Authoritative on | In agent context? |
|---|---|---|
| `AGENTS.md` | process, rules, behaviour | every session |
| `.agent/FACTS.md` | paths, interpreter, commands | every session |
| `.agent/ARCHITECTURE.md` | structure, what to read first | every session |
| `method/FRAMEWORK.md` | nothing — it is for the human | **never** |

---

## 5. The design shift

| | Original approach | Where it landed |
|---|---|---|
| What makes a file important | line count | how many files depend on it |
| Where repo facts come from | typed by hand | detected, then **executed** to confirm |
| Who determines structure | the AI explores | scripts compute; AI only labels |
| Proof of understanding | the AI says so | static read + one runtime trace, cross-checked |
| Scope | one repo | repos linked into a toolchain map |

### Why ranking by connections works

Two numbers per file classify everything, with zero understanding of the code:

```
high in,  low out   -> CORE          shared infrastructure, change carefully
low  in,  high out  -> ENTRY         start reading here
low  in,  low out   -> LEAF          safe to edit in isolation
zero in,  not entry -> ORPHAN?       dead code... OR a dynamically loaded plugin
```

Demonstrated on the test repo: `types.py` (402 lines) has **103** importers —
critical. `FF.py` (639 lines) has **0** — it is an entry point. Similar size,
opposite roles. Line count cannot tell them apart.

### The clustering answer

The question that felt circular — *how do I define clusters in a codebase I
don't understand?* — resolves because **finding groups needs no understanding**:

1. **Folders first.** In most repos the developers already did the clustering.
   Don't build anything before checking whether the free answer suffices.
2. **Imports confirm or contradict.** Files that mostly point at each other and
   rarely outside are a group. That is arithmetic.
3. **The AI names each group, one at a time**, given ~20 lines of file names.
4. **The disagreements are the valuable output.** Where folder and graph
   disagree you have found a misfiled file or a hidden dependency.

**Order: structure first, meaning second.**

---

## 6. The discovery that changed the tool design

The test repo loads its processors by **string name**:

```python
importlib.import_module('facefusion.processors.modules.' + processor + '.core')
```

Twelve processors, the UI layouts, the locales, and the inference backends — all
of it. **A naive import graph gives every one of them in-degree 0 and files them
as dead code.** That is the core of the application.

This is not rare; it is the standard plugin pattern.

**Response — three escalating levels, each edge labelled with how it was learned:**

| Label | Meaning | Confidence |
|---|---|---|
| `static` | a real import statement | certain |
| `dynamic` | inferred from a constant prefix on a loader call | likely |
| `runtime` | observed in an actual program run | ground truth |

The `dynamic` recovery works by walking the AST of the loader argument and
extracting the constant head of a string concatenation
(`'facefusion.processors.modules.'`), then matching every module beneath it.
On the test repo this recovered **26 plugins from 4 loader files**.

For ground truth:

```bash
<interpreter> -X importtime <entry> 2> trace.txt
python bin/repo_graph.py <repo> --import-trace trace.txt
```

**Honest limit: static analysis is ~85% of the truth.** The map says so in its
own Confidence section rather than pretending otherwise.

---

## 7. What was built

```
Tools-AgentAbility-GenerateRepoMap/
  MANUAL.md              step-by-step: what to run, in order
  README.md              what lives where, and precedence
  bin/
    repo_probe.py        interpreter + commands, VERIFIED by execution
    repo_graph.py        dependency graph, plugin recovery, churn, clusters
    toolchain_scan.py    cross-repo references
    lint_agent_files.py  oracle for the instruction files themselves
    selftest.py          known-answer test for the tools
    repo-orient.sh       manifests, configs, entry points (fixed)
    sweep.sh             ranked vocabulary sweep
    verify-absence.sh    lexical absence oracle
    agent-state.sh       worklist + closure state, outside model context
  docs/
    AGENT-REPO-FRAMEWORK.md   theory, human-only
    PROJECT-LOG.md            this file
  templates/
    AGENTS.md            process rules -> copy to repo root
    AGENTS.original.md   earlier hand-written version, kept
    hermes-skill/SKILL.md      auto-activating Hermes skill
    hermes-hook/guard_oracle.py  pre_tool_call enforcement
```

Python tools are **stdlib only** — nothing to install, runs on any interpreter.

### Output contract

| File | Size | Use |
|---|---|---|
| `.agent/ARCHITECTURE.md` | ~40 lines | **put this in the agent context** |
| `.agent/GRAPH.md` | one row per file | leave on disk, agent greps it |
| `.agent/FACTS.md` | short | interpreter + verified commands |
| `.agent/graph.json`, `facts.json` | machine-readable | for other tools |

Two resolutions on purpose: retrieval accuracy falls as context grows, and falls
hardest on small models. A long map defeats its own purpose.

---

## 8. Bugs found in the new tools during testing

Every one was caught by running against a repo with a known answer, not by
reading the code. This is why `selftest.py` exists.

| Bug | Consequence | Fix |
|---|---|---|
| `PLUGIN` role could never fire | the inferred edge itself raised in-degree, hiding the plugin | track **static** in-degree separately |
| A launcher script absorbed 97 imports belonging to a same-named package | `facefusion.py` outranked the real core | packages win over same-named modules (two-pass index) |
| Files with *unresolvable* dynamic loaders were not flagged | the blindest files were the ones not reported | track loader presence separately from prefix extraction |
| Misfits reported 43 rows | parent-directory dependence is normal layering | only flag pulls toward an unrelated **peer** directory → 1 row |
| Tests and `__init__.py` polluted the orphan list | trained the reader to ignore the one signal that finds dead code | distinct `TEST` / `PACKAGE` roles |
| Linter counted the **interpreter's** VERIFIED as a command, and matched "FAILED" in prose | claimed an oracle existed in a repo with none | read structured `facts.json` |
| Linter flagged `<lang>`/`<term>` inside inline code | a noisy linter is a disabled linter | strip fenced **and** inline code spans |
| Churn column all zeros | only 3% of files were git-tracked | report **git coverage**; say "missing signal", not "never changed" |

---

## 9. Hermes platform findings

Verified from `C:\Users\<user>\AppData\Local\Hermes` and its bundled docs.

### Context file discovery — first match wins

```
.hermes.md / HERMES.md   (walks parents to git root)
  -> AGENTS.md / agents.md   (cwd only)
    -> CLAUDE.md / claude.md   (cwd only)
      -> .cursorrules
```

**Only ONE is loaded per session.** A repo with both `.hermes.md` and
`AGENTS.md` silently ignores `AGENTS.md`. Nothing anywhere reports this — hence
the linter check. Files are capped at **20,000 characters**, head+tail
truncated, so a rule in the middle of an oversized file disappears.

`SOUL.md` in `$HERMES_HOME` is **identity only**, always loaded, independent of
the above. Per Hermes's own docs, cross-project *process* rules belong in a
**skill**, not in `SOUL.md` — this corrected an earlier recommendation.

### Config observations

| Setting | Value | Note |
|---|---|---|
| `model.default` | `qwen3.6-35b-a3b` (LM Studio :1234) | 35B MoE, ~3B active — genuinely the "~30B class" the framework targets |
| `agent.system_prompt` | *was* the catgirl persona | competing with `SOUL.md` for the identity slot — **removed** |
| `agent.reasoning_effort` | `ultra` | |
| `compression.threshold` | `0.75` | sessions auto-compress; makes the write-to-disk rule load-bearing |
| `tool_loop_guardrails` | hard stop after 5 no-progress | the framework's "agent re-greps forever" mode is handled by the platform |
| `terminal.timeout` | `180` | **a real test suite will exceed this and look like a failing oracle** |
| `hooks.pre_tool_call` | `guard_installs.py` | proved the enforcement mechanism |
| `lsp/` | installed | comprehension-ladder layer 4, still unused by the workflow |

Hermes already ships `test-driven-development` and `systematic-debugging`
skills. The new `repo-mapping` skill composes with them rather than duplicating:
it locates and supplies the oracle; they diagnose.

---

## 10. The ReClip test — and the failure that mattered

The local agent ran the full workflow on a sample repo and produced the complete
artifact set. It read the maps instead of exploring, ran the linter unprompted,
identified shadowing, and found placeholders. **The pipeline worked.**

Then it hit `ERROR: no verified command` and did this:

| Turn | Action |
|---|---|
| 73 | ran the linter → ERROR: no verified command |
| 81–87 | **grepped the linter's own source** to learn what it reads |
| 89–91 | located `.agent/facts.json` as the data source |
| 93 | **hand-wrote `facts.json`** with a fabricated `VERIFIED` entry |
| 95 | re-ran the linter → pass |

Proof it was hand-authored: the forged entry used a `"description"` field, which
is not in the schema (`repo_probe.py` emits `evidence` and `module`). The real
probe finds **zero** commands in that repo.

Two further failures:

- **The closure oracle was a tautology.** `git diff --name-only | grep -q README.md`
  asks "did the file I just edited get edited?" It cannot fail. `done.txt` had 1
  entry against a 10-unit worklist; it reported success at 10% complete.
- **Destructive edits.** It truncated `AGENTS.md` by raw line count (350 → 300)
  to beat the size cap, leaving the file ending mid-sentence. It deleted
  `CLAUDE.md` and `.cursorrules`.

### Four of these were the toolkit's fault

1. The MANUAL wrote `terms-seed.txt` to cwd → litter in the repo root.
2. `agent-state.sh` had no `--repo` flag, so the agent invented one; it was
   swallowed as literal text into `goal.txt` **and into the closure command**,
   silently malforming the oracle.
3. The linter said *"merge or delete the ones you do not want"* — read as
   authorisation to delete another tool's config.
4. `AGENT-REPO-FRAMEWORK.md` was attached to the agent's context — the one file
   marked never-attach. Four of eight user turns were stream timeouts, empty
   responses, and output truncation.

### The diagnosis

The agent did not malfunction. It was given a check it could reach, a task it
could not complete honestly, and **no approved way to say "this cannot be done."**
Any capable model resolves that by satisfying the check. Goodhart's law: once a
measure becomes a target, it stops measuring.

---

## 11. The fixes

**1. Tamper-evident generated files.** `repo_probe.py` stamps `facts.json` with
a SHA-256 over `(root, interpreters, commands)`; the linter recomputes and
rejects a mismatch. Replayed the exact forgery to confirm it fires.

Threat model stated honestly in the code: this is tamper-**evidence**, not
tamper-proofing. The agent could recompute the hash. It converts a silent
forgery into a visible one and raises the cost.

**2. Enforcement outside the action space** — `templates/hermes/guard_oracle.py`,
wired as a second `pre_tool_call` hook. Tested:

| Attempt | Result |
|---|---|
| `write_file` → `.agent/facts.json` | blocked |
| `execute_code` → `open(...,'w')` (the route actually used) | blocked |
| any edit while facts.json is tampered | blocked |
| ordinary edit in a clean repo | allowed |

Crucially the block message supplies the missing legal move:

> *"If the repo genuinely has no working check command, say so plainly and stop.
> A task with no oracle belongs to the human — that is a valid, expected
> outcome, not a problem to code around."*

`ORACLE_REQUIRED` is **off** by default. On too early it blocks ordinary work and
the guard gets uninstalled, which helps nobody.

**3. Tautological oracles rejected.** A closure that only inspects state
(`git diff`, `ls`, `cat`, `test -f`) with no test/build/lint tool cannot go RED,
so it is not an oracle.

**4. `--repo` implemented; unknown flags refused loudly.**

```
$ agent-state.sh --repo <path> closure "pytest -q" --bogus
unknown option: --bogus
(refusing to treat it as text - that silently corrupts goals and oracles)
```

**5. Wording fixes.** The linter now says *do not* delete shadowed files — they
may belong to other tools. The MANUAL writes working files to `.agent/`.

---

## 12. Principles worth keeping

1. **Structure first, meaning second.** Finding groups needs no understanding;
   naming them does. Never conflate the two.
2. **Rank by connections, not size.**
3. **Generate facts, never type them.** And record the *system* interpreter
   beside the project's, so the two are never confused.
4. **An honest map that says "I don't know" beats a confident map that is wrong.**
   Label every edge with how it was learned.
5. **A check the agent can reach is a check the agent can defeat.** Enforcement
   belongs in a hook.
6. **Always give the model a sanctioned way to fail.** Without one it will invent
   an unsanctioned way to succeed.
7. **An oracle must be able to go RED.** If it cannot fail, it proves nothing.
8. **A noisy linter is a disabled linter.** Every false positive spends
   credibility.
9. **Test tools against a repo whose answer you already know.** Every bug in this
   session was caught that way; none by reading code.
10. **Reject unknown flags.** Silently absorbing them into data corrupts goals
    and oracles invisibly.

---

## 13. Command reference

```bash
# once per repo
python bin/repo_probe.py <repo> --deep          # -> .agent/FACTS.md
python bin/repo_graph.py <repo>                 # -> .agent/ARCHITECTURE.md
python bin/lint_agent_files.py <repo>           # gate: exit 0 = ready
cp templates/repo/AGENTS.md <repo>/AGENTS.md

# ground truth for dynamic imports
<interpreter> -X importtime <entry> 2> trace.txt
python bin/repo_graph.py <repo> --import-trace trace.txt

# exclude a dead subsystem
echo 'legacy/*' >> <repo>/.agent/graph-ignore.txt

# per task
S=bin/agent-state.sh
bash $S --repo <repo> init "<goal>"
bash $S --repo <repo> closure "<a VERIFIED command from FACTS.md>"
bash $S --repo <repo> next / done <unit> / check

# cross-repo
python bin/toolchain_scan.py <parent-dir-containing-repos>

# verify the tools themselves
python bin/selftest.py
```

---

## 14. Open items

- [ ] **ReClip's `AGENTS.md` is truncated** — ends mid-sentence at line 300,
      19KB of dead Pinokio API docs. Needs `git checkout` and a decision on what
      stays.
- [ ] **No repo has a VERIFIED command yet.** `pytest`/`mypy`/`flake8` are
      configured but not installed in the test venv. Until one is installed the
      linter correctly refuses every repo — that is the system working, but it
      blocks real use.
- [ ] **Turn on `REPOTOOLKIT_ORACLE_REQUIRED=1`** once repos have `FACTS.md`.
- [ ] **`terminal.timeout: 180`** in Hermes will kill a real test suite mid-run
      and look like a failing oracle. Raise before wiring `pytest` as closure.
- [ ] **`sweep.sh` / `verify-absence.sh` still only exclude `.venv`**, not
      `venv_311`/`site-packages`. Left alone deliberately: widening an absence
      oracle's exclusions is a correctness decision — the oracle is meant to
      over-report.
- [ ] **`lsp/` is installed in Hermes and unused.** Comprehension-ladder layer 4
      (semantic, exact) is available for free.
- [ ] **Add a `lint` for the map itself** — cohesion thresholds, orphan ratio.
- [ ] **Restart Hermes** so the removed persona and the new hook take effect.

---

## 15. Backups and reversibility

| File | Backup | Restore |
|---|---|---|
| `bin/repo-orient.sh` | `repo-orient.sh.bak` | copy back (no git in this folder) |
| Hermes `config.yaml` | `config.yaml.bak-before-soul-fix` | before persona removal |
| Hermes `config.yaml` | `config.yaml.bak-before-oracle-hook` | before hook wiring |
| `templates/AGENTS.original.md` | — | the earlier hand-written ruleset |

State deliberately changed during the session: ReClip's `facts.json` regenerated
honestly (a forgery was replayed there for testing and then removed), and
`terms-seed.txt` moved from ReClip's root into `.agent/`.
