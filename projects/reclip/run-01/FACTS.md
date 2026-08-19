# FACTS: Reclip

**GENERATED FILE - do not edit by hand.** Regenerate with:

```
python repo_probe.py D:\MyWorld-Sync\012-Utility\Reclip --deep
```

Every row below was produced by inspecting this machine. Rows marked
UNVERIFIED were inferred from config files but not executed - treat them
as claims, not facts.

## Interpreter

No project virtualenv found. The agent must not assume one exists.

_System Python is `3.14.6` at `C:\Python314\python.exe`._
_It is NOT this project's interpreter. Do not install into it._

## Commands

No check commands detected. **This repo has no oracle**, so no task
in it is safely delegable to an agent until one is created.

## Closure oracle

**No verified command available.** Until one exists, an agent cannot
prove it is finished, and a human owns the closure decision.

## Rules that follow from the above

1. Use the interpreter path exactly as written. Do not substitute `python`.
2. Never install into the system interpreter.
3. Never `--force-reinstall` or `--upgrade` against a system-wide
   interpreter: it deletes files before rewriting them and breaks any
   process currently using them.
4. A source build usually means no wheel exists for this Python version,
   not that a compiler is missing.
5. If a row above says UNVERIFIED or FAILED, treat the command as unproven.
   Do not report success on the strength of it.

