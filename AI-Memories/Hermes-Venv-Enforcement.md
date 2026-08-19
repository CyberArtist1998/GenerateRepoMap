# Hermes Venv Enforcement — CORRECTED 2026-08-08

> **This file previously documented a setup that never worked.** The original
> claimed venv enforcement was live after writing a hook to `~/.hermes`. On
> Windows nothing reads `~/.hermes`, so the hook has never executed once.
> Corrected below. See `Hermes-Windows-Paths.md` for the path rule.

## What was attempted

Stop Hermes from installing packages into its own virtualenv instead of the
project's. Two parts: set `code_execution.mode: project`, and add a
`pre_tool_call` hook blocking bare `python` / `pip` in terminal calls.

## Why it did nothing

Both were written to `C:\Users\RedRain2077\.hermes\config.yaml`.

The Hermes home on Windows is `%LOCALAPPDATA%\hermes`
(`hermes_constants.py:_get_platform_default_hermes_home`). `~/.hermes` is the
POSIX default and is never opened on this platform. No error, no warning — the
file is simply not read.

The "10/10 tests passed" in the original note tested `enforce_venv.py` by piping
sample payloads into it directly. That proves the regex works. It does not prove
Hermes ever calls it. The end-to-end check was written down as a to-do and never
performed.

## Verified state as of 2026-08-08

- `python --version` inside Hermes → **exit 0**. No hook fires. Enforcement is off.
- The live config is `C:\Users\RedRain2077\AppData\Local\hermes\config.yaml`.
- Its `code_execution.mode` is whatever that file says — **not** the `project`
  value set in the dead file.
- The live hook is `...\hermes\hooks\guard_installs.py`, matcher
  `(?i)(terminal|bash|shell|exec|python)`. It allows bare `python`.
- `C:\Users\RedRain2077\.hermes` was deleted on 2026-08-08.

## To actually enable it

1. Edit `C:\Users\RedRain2077\AppData\Local\hermes\config.yaml` — the real one.
2. Reconcile with the existing `guard_installs.py` hook. Both match `terminal`;
   adding a second entry runs both. Do not silently replace the existing hook.
3. Put the hook script under `...\hermes\hooks\`, alongside `guard_installs.py`.
4. Restart the gateway — kill by executable path, not process name; the agent
   runs as `python.exe`.
5. **Verify by triggering it.** Ask Hermes to run `python --version`. Blocked
   means it works. Anything else means it does not, regardless of how the config
   file looks.

## The blocking logic (still valid, just never wired up)

Block a bare interpreter at a command start or after a shell separator; allow an
invocation reached by path, and allow environment managers:

```python
ALLOW = re.compile(r'^\s*(uv|uvx|poetry|pipx|conda|mamba|hatch|pdm|rye)\b', re.I)
BARE  = re.compile(r'(?:^|[;&|]\s*|\(\s*)(python3?|py|pip3?)(?:\.exe)?(?=\s|$)', re.I)
```

`.venv\Scripts\python.exe` does not match `BARE` because the preceding character
is a path separator. That is the intended behaviour and must be preserved —
Hermes' own interpreter is invoked by full path in several places.

## Rule

A config file written is not a config file loaded. Enforcement is proven by
observing the block, never by reading back the YAML.
