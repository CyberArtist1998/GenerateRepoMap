# Hermes on Windows — where the config actually lives

**Status:** verified 2026-08-08 against the local checkout at
`C:\Users\RedRain2077\AppData\Local\hermes\hermes-agent`. Hermes Desktop v0.20.0.

Read this before editing any Hermes configuration on this machine.

---

## 1. The rule

**On Windows the Hermes home is `%LOCALAPPDATA%\hermes`. It is NOT `~/.hermes`.**

`~/.hermes` (i.e. `C:\Users\RedRain2077\.hermes`) is the POSIX default. On Windows
nothing reads it. A config placed there is inert — it does not error, it does not
warn, it is simply never opened.

Source — `hermes_constants.py`:

```python
def _get_platform_default_hermes_home() -> Path:
    if sys.platform == "win32":
        local_appdata = os.environ.get("LOCALAPPDATA", "").strip()
        base = Path(local_appdata) if local_appdata else Path.home() / "AppData" / "Local"
        return base / "hermes"
    return Path.home() / ".hermes"          # POSIX only
```

and the config path itself:

```python
def get_config_path() -> Path:
    return get_hermes_home() / "config.yaml"
```

Resolution order for `get_hermes_home()`:

1. context-local override (`set_hermes_home_override()`, per-task)
2. `HERMES_HOME` environment variable
3. platform default — `%LOCALAPPDATA%\hermes` on Windows, `~/.hermes` elsewhere

## 2. Real paths on this machine

| What | Path |
|------|------|
| Hermes home | `C:\Users\RedRain2077\AppData\Local\hermes` |
| Main config | `...\hermes\config.yaml` |
| System prompt / identity | `...\hermes\SOUL.md` |
| Secrets | `...\hermes\.env` |
| OAuth credentials | `...\hermes\auth.json` |
| Hooks | `...\hermes\hooks\` |
| Skills | `...\hermes\skills\` |
| Memories | `...\hermes\memories\` |
| Source checkout | `...\hermes\hermes-agent\` |
| Agent interpreter | `...\hermes\hermes-agent\venv\Scripts\python.exe` |

`C:\Users\RedRain2077\.hermes` — **dead. Deleted 2026-08-08.** Do not recreate it.

## 3. Verify before editing — always

Never assume a config path from documentation, from a Linux tutorial, or from a
previous session's notes. Confirm it in one of these ways:

```powershell
# what the code resolves to
& "$env:LOCALAPPDATA\hermes\hermes-agent\venv\Scripts\python.exe" -c `
  "import sys; sys.path.insert(0, r'$env:LOCALAPPDATA\hermes\hermes-agent'); import hermes_constants as h; print(h.get_config_path())"

# is HERMES_HOME overriding the default?
Get-ChildItem Env: | Where-Object Name -like '*HERMES*'
```

## 4. Verify the edit took effect — always

Writing a config file is not evidence that the config is live. Prove it with an
observable behaviour change:

- Add a hook, then trigger it and confirm it fires.
- Change a setting with a visible effect (e.g. `display.personality`) and look.
- Restart the gateway and re-test — config is read at startup, not per-turn.

A change that produces byte-identical behaviour is a change that did not load.
Three identical failures in a row means stop editing and go find out *which file
is being read* — do not write a fourth variant.

## 5. Killing Hermes fully

The agent runs as `python.exe`, not `hermes.exe`, so filtering by process name
finds nothing and looks like success. Filter by path:

```powershell
Get-CimInstance Win32_Process |
  Where-Object { $_.ExecutablePath -like '*\hermes\*' } |
  Select-Object ProcessId, ExecutablePath          # inspect

Get-CimInstance Win32_Process |
  Where-Object { $_.ExecutablePath -like '*\hermes\*' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
```

The detached gateway survives closing the window. Killing only the UI leaves a
stale gateway serving the old config, which reads exactly like "my edit did
nothing".

## 6. Vision configuration (resolved 2026-08-08)

Main model `qwen3.6-35b-a3b` is text-only. Images route to the `vision_analyze`
tool, which calls the model named in `auxiliary.vision`. That key had been set to
the main model, so every image returned:

```
400 The provided messages contain images, but qwen3.6-35b-a3b does not support image inputs.
```

Working configuration:

```yaml
providers:
  lmstudio:
    api: http://127.0.0.1:1234/v1
    default_model: qwen3-coder-next
    models:
      - qwen3-coder-next
      - qwen3.6-35b-a3b
      - qwen3-vl-4b-instruct
    name: LM Studio

auxiliary:
  vision:
    provider: lmstudio
    model: qwen3-vl-4b-instruct     # MUST be vision-capable, not the main model
    timeout: 120
    download_timeout: 30
```

Requires `qwen3-vl-4b-instruct` loaded in LM Studio with the server running on
port 1234. The model string must match LM Studio's id exactly — check the CURL
dropdown in the Developer tab, or `GET http://127.0.0.1:1234/v1/models`.

`auxiliary.vision.provider` takes a **bare** provider name from the `providers:`
dict. Not `custom`, and not `custom:<name>` — the prefixed form is only valid in
the top-level `model:` section. An unresolvable name does not error; it falls
through the auto-chain to the main provider, reproducing the exact error above.

## 7. When vision fails, do not fake it

If `vision_analyze` or `browser_vision` errors, the correct response is to report
the error and fix the routing. Reporting image dimensions, dominant colours,
bounding boxes, or pixel counts is not looking at an image, and presenting it as
analysis is misleading. Asking the user to describe their own screenshot is a
last resort, not a first one.

Routing-independent fallback, if ever needed — POST the image base64-encoded to
LM Studio directly:

```python
payload = {
    "model": "qwen3-vl-4b-instruct",
    "messages": [{"role": "user", "content": [
        {"type": "text", "text": question},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
    ]}],
}
# POST http://127.0.0.1:1234/v1/chat/completions
```

Stdlib only. Independent of every Hermes setting.

## 8. Venv enforcement — NOT active

The venv-enforcement hook written on 2026-08-08 went to `~/.hermes` and has never
run. Confirmed: `python --version` executes normally inside Hermes.

The live hook is `...\hermes\hooks\guard_installs.py`, matcher
`(?i)(terminal|bash|shell|exec|python)`, which permits bare `python`.

Porting the venv rules means adding them to the **real** `config.yaml` and
reconciling with `guard_installs.py` rather than replacing it. Not done yet.

Note: a full-path interpreter call such as
`C:\...\venv\Scripts\python.exe script.py` is *not* a bare invocation and should
remain allowed by any such hook.

---

## The general lesson

Every wrong conclusion in this episode came from asserting something unverified:

1. A config path taken from Linux docs and never checked against the code.
2. A hook declared "10/10 passing" — the tests exercised the script directly
   against sample strings; it was never once triggered through Hermes.
3. "The model can't see images" — false. A vision model was loaded and reachable
   the whole time; only one config line was wrong.
4. Pixel statistics offered as a substitute for reading an image.

Check the mechanism before describing it. State which file you read, which
process you inspected, which command you ran. If it was not verified this
session, say so.
