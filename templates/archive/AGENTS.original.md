# AGENTS.md

> Drop this in the repo root. Fill every `<...>` placeholder before first use.
> An unfilled placeholder is worse than no file — the agent will invent a value.

## Project

- **What it is:** <one sentence>
- **Stack:** <language / framework / runtime version>
- **Package manager:** <npm | pnpm | yarn | uv | poetry>
- **Source roots:** <e.g. src/, server/, packages/*/src>

## Commands

| Purpose | Command |
|---|---|
| Install | `<...>` |
| Build | `<...>` |
| Typecheck | `<...>` |
| Test | `<...>` |
| Lint (autofix) | `<...>` |
| Run locally | `<...>` |

Run the build after every file you modify. A green build is the only evidence that an edit is correct.

## Layout

| Path | Responsibility |
|---|---|
| `<src/app>` | <...> |
| `<src/services>` | <...> |
| `<src/components>` | <...> |
| `<src/config>` | <...> |

- **Entry point:** `<...>`
- **Config and feature flags live in:** `<...>`
- **Environment variables declared in:** `<...>`

## Landmines

- <e.g. `DeckGLMap.ts` is 4000 lines — never read it whole, use line ranges>
- <e.g. anything under `generated/` is build output, never edit>
- <e.g. the server rejects requests without an auth header regardless of client state>

---

# Operating rules

## 1. Tool preference order

Use the cheapest tool that answers the question. Do not skip down the list.

1. `rg` — exact text. Always with `-w` for identifiers, `-t <lang>` to scope, `-n` for line numbers.
2. `ast-grep` — code shape, when text matching is too noisy.
3. Typechecker / LSP — definitions and references, when you need certainty.
4. `git log -S "<term>"` — when you need to know why or when something was added.
5. Run the code — when static analysis is inconclusive.

Never `cat` a file to search it. Never read a whole file when a line range suffices.

## 2. State lives on disk, not in this conversation

Before any read, check `.agent/done.txt`. After any read, append to it.

```
.agent/worklist.txt    # pending units, one per line
.agent/done.txt        # completed units
.agent/findings.md     # located items, file:line, one per line
.agent/questions.md    # escalations
.agent/decisions.md    # human answers (read-only for you)
```

Never keep an important result only in your reply. Write it to a file first.

## 3. Locate before you change

Do not edit anything until `.agent/findings.md` is complete.

Procedure:
1. Broad sweep with guessed vocabulary.
2. Open the top 3 hits. Extract the **project's actual identifiers**.
3. Re-sweep on those real identifiers.
4. Find each identifier's definition, then all its references.
5. Stop only when the closure condition is met (see rule 6).

## 4. Minimal diff — strict order

1. Change the **definition**. One line if possible.
2. Change the **config or data**.
3. Change the **call sites**.
4. **Delete** code.

Do not use rung 3 until rungs 1 and 2 are proven impossible. Do not use rung 4 without explicit human approval. State which rung you are on before every edit.

## 5. One unit at a time

One file per task. After each file:

```
<typecheck command>
git add <file> && git commit -m "<what changed>"
```

If the build fails: revert that file only (`git checkout -- <file>`), then retry with a smaller change. Do not proceed with a red build. Do not batch multiple files into one commit.

Edit bottom-up: leaf components → services → config. Removing a definition before its usages guarantees a broken intermediate state.

## 6. Stopping

You are done only when an **oracle** says so:

- the verification sweep returns zero hits, **and**
- the build is green, **and**
- the test suite has been run and each failure classified.

"I have not found anything new" is not a stopping condition. "The worklist is empty" is only valid if the worklist was provably complete.

## 7. Ambiguity — escalate, do not guess

A hit counts only if it sits inside a control-flow guard (`if`, `&&`, `?:`, `?.`, early return) or a configuration collection. A hit inside a string literal, comment, or data-formatting expression does not count.

If you cannot classify a hit, append it to `.agent/questions.md`:

```
## <file>:<line>
<3 lines of surrounding code>
Q: <the specific question>
```

Then continue with the items you are certain about. Do not block. Do not guess.

## 8. Never

- Never install a package without first confirming it exists (`npm view <pkg>` / `pip index versions <pkg>`). If a name cannot be verified, report that and stop.
- Never invent a file path, function name, or command. If you have not read it, say so.
- Never assume a green build means correct behaviour. Say explicitly what still needs manual verification.
- Never modify files under `<generated/ | dist/ | node_modules/>`.
- Never rewrite git history, force-push, or amend commits you did not create.
- Never edit more than one file between commits.

## 9. Report format

End every task with:

```
CHANGED:   <files, one per line>
COMMITS:   <hashes>
BUILD:     pass | fail
TESTS:     <n passed, n failed — and whether failures were expected>
UNVERIFIED: <what a human still needs to check by hand>
QUESTIONS: <count in questions.md>
```
