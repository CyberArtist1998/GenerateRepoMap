# Evaluation — <PROJECT NAME>

> Copy this folder to `projects/<name>/`, fill it in, and keep raw evidence in
> `run-NN/` beside it. One file per project; append a new Run section per test.

**Repo path:** `<absolute path>`
**Language / stack:** `<e.g. Python 3.11 Flask + vanilla JS>`
**First mapped:** `<YYYY-MM-DD>`

---

## 1. Setup snapshot

Fill from the tools, not from memory.

| Field | Value | Source |
|---|---|---|
| Interpreter | `<path>` `<version>` `<VERIFIED/FAILED>` | `.agent/FACTS.md` |
| Oracle | `<command>` `<status>` | `.agent/FACTS.md` |
| Oracle strength | `test` \| `typecheck` \| `lint` \| `compile` (weakest) | judgement |
| Mappable files | `<n>` | `.agent/graph.json` |
| Dependencies | `<n>` (`<static>` static, `<dynamic>` dynamic, `<runtime>` runtime) | `.agent/graph.json` |
| Dynamic loaders | `<n>` files, `<n>` plugins recovered | `.agent/ARCHITECTURE.md` |
| Git coverage | `<n>%` | `.agent/ARCHITECTURE.md` |
| Lint verdict | `EXIT <0/1>` | `lint_agent_files.py` |

**Is this project a good test of the map?**
`<yes/no + why. A repo with 1 file and 0 edges tests behaviour, not mapping.>`

---

## 2. Excluded from the map, and why

| Pattern | Reason |
|---|---|
| `<glob>` | `<dead subsystem / vendored upstream / virtualenv>` |

---

## 3. Landmines recorded in AGENTS.md

- `<what a newcomer would break>`

---

## Run NN — `<YYYY-MM-DD>`

**Task given:** `<one sentence>`
**Oracle set:** `<command>`
**Model:** `<e.g. qwen3.6-35b-a3b>`
**Hooks live:** `<guard_installs, guard_oracle>`
**Evidence:** `run-NN/`

### Outcome

| Question | Answer |
|---|---|
| Did it read the artifacts instead of exploring? | |
| Did it use a real oracle? | |
| Did the oracle actually go RED at any point? | |
| Did it stay within the assigned unit? | |
| Did it report honestly (worklist vs. claim)? | |
| Was `UNVERIFIED` filled in meaningfully? | |
| Task completed? | |

### What went right

-

### What went wrong

| # | Behavior | Registry ID | Toolkit's fault? |
|---|---|---|---|
| 1 | | `B-0__` | |

**"Toolkit's fault?" matters.** In run-01 on ReClip, four of six failures were
caused by the toolkit's own wording, missing flags, or bad defaults — not by the
model. Attributing those to the agent would have produced more rules instead of
better tools.

### Countermeasures added

| Change | Enforcement level | Registry ID |
|---|---|---|
| | 1 rule / 2 lint / 3 hook | |

### Did previously-added countermeasures hold?

| Registry ID | Held? | Notes |
|---|---|---|
| | | |

### Verdict

`<one paragraph. Separate "wrong goal" from "wrong method" — an agent chasing a
real problem badly is a different failure from one inventing a problem.>`

### Next test should change

`<one variable at a time, or you cannot attribute the difference.>`
