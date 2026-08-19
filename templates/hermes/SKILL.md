---
name: repo-mapping
description: Map an unfamiliar repo before reading or editing its code.
version: 0.1.0
author: RedRain2077, Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [repo, dependency-graph, onboarding, oracle, debugging]
    related_skills: [test-driven-development, systematic-debugging, plan]
---

# Repo Mapping

## Overview

Generate a dependency map and a verified command list for a repository, then work
from those artifacts instead of exploring the codebase.

Exploring is expensive and unreliable. The map is computed by scripts — exact,
deterministic, and cheap. Read the artifacts; do not rediscover them.

Toolkit location: `D:/MyWorld-Sync/011-AI/Tools-Generate-RepoMap`

## When to Use

Load this skill when any of these is true:

- You are asked to work in a repository you have not mapped in this session
- You need to know which file to open and no one has told you
- You are about to answer "where is X handled?" or "what does this project do?"
- You are about to delete, remove, or clean up code
- You need a command that proves a task is finished
- The user says: map this repo, orient me, where should I start, what depends on
  this, is this dead code, what breaks if I change this

Do **not** use for: a single known file edit, or a repo whose `.agent/ARCHITECTURE.md`
is present and stamped with the current commit.

## The rule that matters most

**Never search for structure that is already computed.** If `.agent/ARCHITECTURE.md`
exists and is current, read it. Running a broad `grep` to rediscover what the map
already states is wasted context and a worse answer.

## Procedure

### 1. Check whether the map exists and is current

```bash
python <toolkit>/bin/lint_agent_files.py .
```

Exit 0 means the artifacts are usable. Exit 1 prints exactly what is wrong.
If it reports STALE or missing, regenerate before doing anything else.

### 2. Generate what is missing

```bash
python <toolkit>/bin/repo_probe.py . --deep     # -> .agent/FACTS.md
python <toolkit>/bin/repo_graph.py .            # -> .agent/ARCHITECTURE.md
```

### 3. Read, in this order

| File | Read it? |
|---|---|
| `.agent/FACTS.md` | Yes — interpreter and verified commands |
| `.agent/ARCHITECTURE.md` | Yes — entry points, core files, subsystems |
| `.agent/GRAPH.md` | **No.** Grep it for one path when needed |

### 4. Obey the roles in the map

| Role | Meaning | What to do |
|---|---|---|
| `ENTRY` | start of execution | read first |
| `CORE` | many files import it | high blast radius; state the count before editing |
| `LEAF` | isolated | safest to edit |
| `PLUGIN` / `RUNTIME-LOADED` | loaded by name at runtime | **never call this dead code** |
| `ORPHAN?` | nothing references it | candidate for dead code, unconfirmed |

## Critical: dynamically loaded code

Files marked `PLUGIN` or `RUNTIME-LOADED` are reached by string name, not by an
import statement. A reference search finds nothing and appears to prove they are
unused. **They are not.** Deleting one removes working functionality with no
compile error and no failing import.

Before calling anything dead, confirm it is not in the map's dynamic list and
say plainly that you checked.

## Oracles

Never report a task finished without a command proving it. Take one from the
Commands table in `.agent/FACTS.md` — only rows marked `VERIFIED`.

If FACTS.md lists no verified command, say so and stop. A task with no oracle is
not agent-ready and belongs to the human.

For a bug fix, the oracle is the failing repro flipping to passing:

```bash
<interpreter> -m pytest <path>::<test>
```

Confirm it fails **before** you change anything. A repro that already passes
means you have the wrong repro.

Once the map has told you WHERE to look, hand the actual RED-GREEN-REFACTOR loop
to the `test-driven-development` skill, and hypothesis-driven isolation to
`systematic-debugging`. This skill's job ends at "here is the file and here is
the oracle" — it locates, they diagnose.

## Reporting

End with:

```
CHANGED:    <files>
RUNG:       <which minimal-diff rung>
ORACLE:     <command> -> <exit code>
UNVERIFIED: <what a human still must check by hand>
```

`UNVERIFIED` is required. A green oracle cannot cover runtime behaviour or
anything reached only through a dynamic loader.
