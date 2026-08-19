# Local Agent Repo Navigation — Framework & Checklist

**Scope:** general framework for running a small local model (~30B class) against an unfamiliar codebase for any task: locate, modify, refactor, remove, extend.

**Assumed agent capability:** shell execution + file read/write. Nothing else is required.

**Core thesis:** the binding constraint is not the model's intelligence. It is **verifiability**. Structure every task so that each step has a cheap mechanical oracle. Delegate where an oracle exists. Do not delegate where none does.

---

## 1. The comprehension ladder

Seven layers of repo understanding, cheapest and most exact first. Most agent failures are starting at layer 2 and never leaving it.

| # | Layer | Tool | Answers | Cost | Exactness |
|---|-------|------|---------|------|-----------|
| 1 | Structural | `tree`, `wc -l`, manifests | "What is this project?" | seconds | exact |
| 2 | Lexical | `ripgrep` | "Where does this text appear?" | seconds | exact, noisy |
| 3 | Syntactic | `ast-grep`, tree-sitter | "Where does this *shape* appear?" | seconds | exact, precise |
| 4 | Semantic (static) | LSP, `tsc`, type checker | "What is actually connected?" | minutes | exact, misses dynamic |
| 5 | Historical | `git log -S`, `blame` | "Why does this exist?" | seconds | exact |
| 6 | Dynamic | run it, trace, coverage | "What actually executes?" | minutes | ground truth |
| 7 | Associative | embeddings / vector search | "What relates to this idea?" | hours to set up | fuzzy |

**Rule:** never invoke layer 7 to answer a question layers 1–5 already answer. Embeddings solve exactly one problem — you don't know the project's vocabulary. Once layer 2 reveals the real identifiers, layers 3–5 are strictly better.

**Layer 6 is the most under-used and highest-value.** Static analysis cannot see dynamic dispatch, event-emitter wiring, DI containers, or string-constructed calls. Running the code can. Instrument the function of interest to `throw` or `console.trace()`, exercise the app, and every live call site announces itself with a stack trace.

---

## 2. The verifiability principle

Assign work by whether a mechanical oracle exists.

| Oracle available | Owner | Loop until |
|---|---|---|
| Compiler / type check | Agent | exit 0 |
| Test suite | Agent | green |
| Re-sweep returns zero hits | Agent | zero |
| Lint / format | Agent | clean |
| **None** | **You, or a frontier model** | judgement |

Discovery has no native oracle, which is why small models fail at it. But an oracle can often be **constructed** — see §7. If you can construct one, discovery becomes delegable. If you can't, don't delegate it.

---

## 3. The artifact rule

**Every phase writes a file. Nothing important lives only in context.**

Context is a cache. Disk is memory. This single rule fixes:

- state-block corruption (state lives in a file, not in a token stream)
- loop repetition (worklist file is checked and appended)
- crash resumability (restart reads the file)
- reviewability (you read the artifact, not a 200-turn transcript)
- context exhaustion (findings are summarized to disk, then dropped)

Minimum artifact set per task:

```
.agent/
  REPO-MAP.md        # written once per repo, committed
  worklist.txt       # pending units, one per line
  done.txt           # completed units
  findings.md        # what was located, with file:line
  questions.md       # escalations awaiting your answer
  decisions.md       # your answers, appended
```

---

## 4. Four-phase pipeline

### Phase 0 — Orient (once per repo, human or frontier model)

Produce `REPO-MAP.md` and commit it. This is the highest-ROI intervention in the entire framework: ~300 tokens per session that replaces hundreds of exploratory file reads.

Contents: what the project does, stack and package manager, directory→responsibility table, entry points, where config and env vars live, build/test/lint commands, known landmines.

Run `repo-orient.sh` to generate the skeleton, then fill in the judgement parts yourself.

### Phase 1 — Locate

Goal: a complete, file:line-precise list of what must change. Output: `findings.md`.

Two rounds, always:

1. **Seed sweep** — generic vocabulary you guess. Produces noisy hits.
2. **Read the top 3 hits** and extract the project's *real* identifiers.
3. **Targeted sweep** on the real identifiers. Now precise.
4. **Reference expansion** — for each identifier, find its definition and all references.
5. **Closure check** — see §7.

Step 2 is the part grep alone cannot do and the part small models skip.

### Phase 2 — Change

Governed by the minimal-diff ladder (§5). One unit per task, one commit per unit, verified before proceeding.

### Phase 3 — Verify

Mechanical re-check (`verify-absence.sh`), then build, then test, then **run the application and exercise the affected paths**. Compilation success is not behavioural success.

---

## 5. The minimal-diff ladder

**This is the single biggest lever in the whole framework.** Prefer, strictly in order:

1. **Change the definition.** One line. Blast radius zero. Reversible with `git revert`.
2. **Change the config or data.** Flip a flag, edit an array, change an env var.
3. **Change the call sites.** N edits, N chances to break something.
4. **Delete code.** Maximum blast radius: imports, shared utilities, types, tests.

The agent must not proceed to rung 3 until rungs 1 and 2 are proven impossible, and must not proceed to rung 4 until you approve.

Worked example — neutralizing a feature gate:

```ts
// Rung 1: one line at the definition
export function hasPremiumAccess(): boolean {
  return true;   // NEUTRALIZED — was: return user?.tier === 'pro'
}
```

versus removing the `if` at 40 call sites. The one-line version dissolves six distinct failure modes at once: shared-utility deletion, edit ordering, orphaned imports, output truncation, block-removal syntax errors, and payment-lifecycle breakage. Dead-branch cleanup becomes an optional later pass, not a prerequisite.

---

## 6. Context discipline

Long context is not a fix, and raising it can make things worse.

- **Read ranges, not files.** `sed -n '90,140p'`, not `cat`.
- **Summarize to disk immediately**, then drop the raw content.
- **One task = one file = one commit = fresh session** where the agent supports it.
- **Cap response length.** Runaway generation is a common cause of context overflow.
- **Never paste tool output back into a prompt.** Write it to a file, reference the path.

Two concrete costs of large context on local hardware:

- **KV cache** scales linearly with context length. A 256K window on a 30B-class model is tens of GB of cache; it will collapse your tokens/sec or force it out of VRAM.
- **Retrieval accuracy degrades** with context length, more sharply for smaller models. Filling the window with the whole repo makes the model *worse* at finding things in it.

---

## 7. Stopping criteria — know which kind you have

| Kind | Statement | Strength | Valid when |
|---|---|---|---|
| Loop detection | "I've seen this file before" | Weak | Only prevents waste, proves nothing |
| Enumeration closure | "The worklist is empty" | Medium | Only if the worklist was complete to begin with |
| **Oracle closure** | "The re-sweep returns zero / build is green / trace is silent" | **Strong** | Always — this is the only one worth trusting |

**Design tasks so that oracle closure is available. If it isn't, the task is not agent-ready.**

Three constructible oracles:

1. **Lexical absence.** After changes, re-run the sweep and assert zero hits outside an allowlist. Proves lexical completeness. Does not prove semantic completeness.
2. **Runtime silence.** Instrument the target function to `throw`, exercise every screen and path, confirm nothing fires. Catches the dynamic-dispatch cases static analysis cannot.
3. **Coverage delta.** Run tests with coverage before and after; branches that were covered and are now unreachable are the dead code you created.

---

## 8. Ambiguity protocol

The agent must never guess on classification. Give it a rule and an escape hatch.

**Rule template:** "A hit counts as a match only if it appears inside a control-flow guard (`if`, `&&`, `?:`, `?.`, early return) or a configuration collection. A hit inside a string literal, comment, or data-formatting expression is not a match."

**Escape hatch:** unresolvable items append to `.agent/questions.md` with a 3-line code excerpt. The agent continues with certain items and does not block. You answer in batch by appending to `.agent/decisions.md`.

Batching matters: per-item interruption makes the process unusable if the false-positive rate is high.

---

## 9. Failure mode catalogue

| Symptom | Root cause | Countermeasure |
|---|---|---|
| Agent re-greps the same thing | No external state | `.agent/done.txt`, checked before every read |
| Agent never terminates | Loop detection used as closure | Construct an oracle (§7) |
| Context overflows, re-prefills forever | Raw tool output kept in context | Artifact rule (§3), response cap |
| Recommends a package that doesn't exist | Model hallucinates tooling | **Verify every package before install: `npm view <pkg>` / `pip index versions <pkg>`. Non-negotiable.** |
| Misses gates entirely | Dynamic dispatch, string-built calls, DI wiring | Runtime tracing (layer 6) |
| Misses server-side logic | File list scoped to `src/` only | Include all packages; check `package.json` workspaces, `tsconfig` refs |
| Compiles but breaks at runtime | Build treated as sufficient oracle | Smoke test; watch network tab for 401/403 |
| Deletes a shared utility | Function used by non-target code too | Minimal-diff ladder (§5); check all references before deleting |
| Transient build failures mid-edit | Import removed before usage | Bottom-up order: leaves → services → config |
| Truncated diff corrupts a file | Output token limit hit on a large file | Split by logical group; commit between groups; or use `sed` for pure line deletion |
| Tests fail after change | Tests asserted the old behaviour | Expect this; update or remove those tests deliberately |
| App got slower | Removed gate was also a lazy-load boundary | Profile after; re-add loading boundaries if needed |
| Orphaned CSS, imports, i18n keys | Removal leaves dead references | `eslint --fix`, `ts-prune`/`knip`, `depcheck` as a cleanup pass |
| Modified fork isn't distributable | License not checked | Read `LICENSE` **before** starting |

The fourth row deserves emphasis: the research this framework was built from recommended nine code-search tools, at least two of which do not exist. Treat any tool recommendation from a model as unverified until you check the registry.

---

## 10. Checklist

### Pre-flight (once per repo)

- [ ] Read `LICENSE`. Confirm the intended change and its distribution are permitted.
- [ ] `git status` clean. Create a working branch.
- [ ] Confirm build and test commands run green **before** any change.
- [ ] Run `repo-orient.sh`; complete `REPO-MAP.md` by hand; commit it.
- [ ] Identify all source roots (workspaces, monorepo packages, `server/`, `scripts/`). Confirm none are missed.
- [ ] Write `AGENTS.md` into the repo root.
- [ ] Verify every tool/package you plan to install actually exists.

### Per task

- [ ] Task fits in one file, or is split until it does.
- [ ] An oracle is identified before starting. If none exists, you own the task.
- [ ] `.agent/worklist.txt` populated; closure condition written down explicitly.
- [ ] Seed sweep → read top hits → targeted sweep on real identifiers.
- [ ] Reference expansion from each definition.
- [ ] Ambiguous items escalated to `questions.md`, not guessed.
- [ ] `findings.md` complete with file:line before any edit is made.

### Per edit

- [ ] Minimal-diff ladder respected; rung 1 or 2 attempted first.
- [ ] One file, one logical change.
- [ ] Build/typecheck run immediately after.
- [ ] `git commit` on success. On failure, revert that file only and retry smaller.
- [ ] Bottom-up order maintained (leaves before services before config).

### Post

- [ ] `verify-absence.sh` returns zero.
- [ ] Full build green.
- [ ] Full test suite run; failures triaged as intended-vs-regression.
- [ ] **Application launched and affected paths exercised by hand.**
- [ ] Console and network tab checked for new errors.
- [ ] Performance spot-checked if loading behaviour changed.
- [ ] Cleanup pass: `eslint --fix`, unused imports, dead CSS, orphaned i18n keys.
- [ ] `findings.md` committed as documentation of what changed and why.

---

## 11. Division of labour

| Work | Owner | Why |
|---|---|---|
| Orient / write `REPO-MAP.md` | You or frontier model | No oracle, high branching |
| Seed sweep | Script | Deterministic |
| Read hits, extract real identifiers | You or frontier model | Judgement |
| Targeted sweep, reference expansion | Script or local agent | Deterministic |
| Classify ambiguous hits | You | Semantic, project-specific |
| Apply edits | Local agent | Narrow, oracle-backed |
| Build/test loop | Local agent | Fully oracle-backed |
| Runtime verification | You | Requires a human looking at a screen |

The local model is a competent editor and a poor explorer. Structure the work so it only ever edits.
