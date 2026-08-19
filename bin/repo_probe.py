#!/usr/bin/env python3
"""
repo_probe.py - Detect a repository's real interpreter and check commands,
then WRITE THEM DOWN ONLY AFTER RUNNING THEM.

WHY THIS EXISTS
---------------
Hand-written facts about a machine rot silently and are never noticed until an
agent acts on them. The failure that motivated this tool: an instruction file
confidently stated

    "a Python 3.14 venv at venv/"
    launch with: ./venv/Scripts/python.exe app.py

when the project's venv was at venv_311/ and held Python 3.11.9. The author had
read the SYSTEM Python's version (3.14) and written it down as the PROJECT's.
Every command in that file failed, and the file itself had a section titled
"Verify before you claim".

A human cannot be trusted to keep these in sync across many repos. A script can.

WHAT IT DOES
------------
Detects, then VERIFIES by execution:

    * the project interpreter (venv/.venv/venv_*/env, Windows and POSIX layouts)
    * its true version, by running it - never inferred from the directory name
    * test / lint / typecheck / format / build commands, from real config files
    * the package manager, from which lockfile is actually present

Each row is stamped:

    VERIFIED    the tool was invoked and answered
    FAILED      the tool was invoked and did not answer (present but broken)
    UNVERIFIED  inferred from config, not executed (see --deep)

IMPORTANT - what VERIFIED means here
------------------------------------
VERIFIED means "this command is invocable" - the tool exists and responds to
--version. It does NOT mean the test suite passes or the code type-checks.
Those are the agent's job to run and are a different question. Probing must be
fast and free of side effects, so it never runs a suite.

USAGE
-----
    python repo_probe.py <repo-root>
    python repo_probe.py <repo-root> --deep     # also run each tool's --version

Writes .agent/FACTS.md - the per-repo facts file. It is GENERATED. Never edit
it by hand; fix the repo or this script and regenerate.

Standard library only. Python 3.9+.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# Directory names that commonly hold a project virtualenv, most specific first.
VENV_DIR_HINTS = ("venv", ".venv", "env", ".env", "virtualenv")

# How long any single probe command may take. Long enough for a cold-start
# interpreter on Windows, short enough that a hung tool cannot stall the run.
PROBE_TIMEOUT = 30


def integrity_stamp(data: dict) -> str:
    """Fingerprint the load-bearing fields of a facts record.

    WHY: an agent that cannot satisfy the oracle will try to satisfy the CHECK
    instead. Observed in the wild: a model read the linter's source, found that
    it reads facts.json, hand-wrote a facts.json containing a fabricated
    VERIFIED command, and re-ran the linter to get a pass. The repo had no
    working check command at all.

    This stamp makes that edit LOUD instead of silent. The linter recomputes it
    and refuses a mismatch.

    Be clear about the threat model: this is tamper-EVIDENCE, not tamper-proofing.
    Anything the agent can read, it can recompute. A determined model could
    regenerate the stamp. It raises the cost from "change one word in a JSON
    file" to "understand and reproduce the hashing scheme", and - more usefully -
    it converts a silent forgery into a visible one during human review.

    Real enforcement lives outside the agent's reach: run the linter from a
    pre-tool-call hook (see hooks/require_clean_lint.py), where a passing result
    cannot be manufactured by editing a file.
    """
    import hashlib
    material = json.dumps(
        {
            "root": data.get("root", ""),
            "interpreters": data.get("interpreters", []),
            "commands": [
                {k: c.get(k) for k in ("role", "command", "status", "evidence")}
                for c in data.get("commands", [])
            ],
        },
        sort_keys=True, separators=(",", ":"),
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]


def run(cmd: list[str], cwd: Path, timeout: int = PROBE_TIMEOUT):
    """Run a command and return (ok, first_line_of_output).

    Never raises. A probe that explodes must degrade to UNVERIFIED, not take
    the whole run down with it.
    """
    try:
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                                timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return False, ""
    text = (result.stdout or "") + (result.stderr or "")
    first = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
    return result.returncode == 0, first


# ---------------------------------------------------------------------------
# Interpreter discovery
# ---------------------------------------------------------------------------

# Never descend into these looking for a project environment.
_SKIP_SUBDIRS = {".git", ".agent", "node_modules", "__pycache__", "dist", "build",
                 "out", "coverage", ".idea", ".vscode", "cache", "logs", "downloads"}


def is_excluded_subdir(name: str) -> bool:
    return name in _SKIP_SUBDIRS or name.startswith(".")


def find_interpreters(root: Path) -> list[dict]:
    """Locate every candidate Python interpreter belonging to this repo.

    Scans known venv directory names AND any directory whose name starts with
    'venv' or 'env' - which is how 'venv_311', 'venv-3.11', 'env39' get found.
    The version is ALWAYS obtained by executing the binary, never parsed from
    the directory name: 'venv_311' is a naming convention, not a guarantee.
    """
    candidates: list[Path] = []
    seen: set[Path] = set()

    def consider(directory: Path) -> None:
        # Windows puts the interpreter in Scripts/, POSIX in bin/.
        for relative in ("Scripts/python.exe", "bin/python3", "bin/python",
                         "Scripts/python"):
            binary = directory / relative
            if binary.is_file() and binary not in seen:
                seen.add(binary)
                candidates.append(binary)

    # Scan the root AND one level down. A launcher/wrapper repo commonly keeps
    # the real application in a subdirectory with its own environment
    # (app/env, server/.venv, backend/venv). Scanning only the root reports
    # "no interpreter found" for the exact repos that most need one, and the
    # agent then falls back to whatever python is first on PATH.
    search_dirs = [root]
    try:
        search_dirs += [
            e for e in root.iterdir()
            if e.is_dir() and not e.is_symlink()
            and not is_excluded_subdir(e.name)
        ]
    except OSError:
        pass

    for base in search_dirs:
        for hint in VENV_DIR_HINTS:
            if (base / hint).is_dir():
                consider(base / hint)
        try:
            for entry in base.iterdir():
                if entry.is_dir() and entry.name.lower().startswith(
                        ("venv", "env", ".venv")):
                    consider(entry)
        except OSError:
            pass

    results = []
    for binary in candidates:
        ok, line = run([str(binary), "--version"], root)
        version = ""
        match = re.search(r"(\d+\.\d+\.\d+)", line)
        if match:
            version = match.group(1)
        results.append({
            "path": binary.relative_to(root).as_posix(),
            "version": version or "(no answer)",
            "status": "VERIFIED" if ok and version else "FAILED",
        })
    return results


def system_python(root: Path) -> dict:
    """Record the SYSTEM interpreter separately and label it clearly.

    Recorded specifically so a reader can see it is NOT the project's. Confusing
    these two is the exact bug this tool exists to prevent, so the fix is to
    show both side by side rather than to hide one.
    """
    ok, line = run([sys.executable, "--version"], root)
    match = re.search(r"(\d+\.\d+\.\d+)", line)
    return {
        "path": sys.executable,
        "version": match.group(1) if match else "(no answer)",
        "status": "VERIFIED" if ok else "FAILED",
    }


# ---------------------------------------------------------------------------
# Command discovery
# ---------------------------------------------------------------------------

def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def detect_python_commands(root: Path, interpreter: str | None) -> list[dict]:
    """Infer Python check commands from the config files actually present.

    Config presence is the evidence. A repo carrying a mypy.ini is a repo whose
    author intended mypy to run, whether or not anyone has run it lately.
    """
    py = interpreter or "python"
    found: list[dict] = []

    pyproject = read_text(root / "pyproject.toml")
    setup_cfg = read_text(root / "setup.cfg")
    tox_ini = read_text(root / "tox.ini")

    def add(role: str, cmd: str, evidence: str, module: str) -> None:
        found.append({"role": role, "command": cmd, "evidence": evidence,
                      "module": module})

    # --- tests
    if (root / "pytest.ini").is_file() or "[tool.pytest" in pyproject \
            or "[pytest]" in setup_cfg or "[pytest]" in tox_ini \
            or (root / "tests").is_dir() or (root / "test").is_dir():
        evidence = "pytest.ini" if (root / "pytest.ini").is_file() else \
            "tests/ directory" if (root / "tests").is_dir() else "pyproject/setup.cfg"
        add("test", f"{py} -m pytest", evidence, "pytest")

    # --- type check
    if (root / "mypy.ini").is_file() or "[tool.mypy]" in pyproject \
            or "[mypy]" in setup_cfg:
        evidence = "mypy.ini" if (root / "mypy.ini").is_file() else "pyproject/setup.cfg"
        add("typecheck", f"{py} -m mypy .", evidence, "mypy")
    if (root / "pyrightconfig.json").is_file():
        add("typecheck", "pyright", "pyrightconfig.json", "")

    # --- lint
    if (root / ".flake8").is_file() or "[flake8]" in setup_cfg or "[flake8]" in tox_ini:
        evidence = ".flake8" if (root / ".flake8").is_file() else "setup.cfg/tox.ini"
        add("lint", f"{py} -m flake8", evidence, "flake8")
    if (root / "ruff.toml").is_file() or (root / ".ruff.toml").is_file() \
            or "[tool.ruff]" in pyproject:
        evidence = "ruff.toml" if (root / "ruff.toml").is_file() else "pyproject.toml"
        add("lint", f"{py} -m ruff check .", evidence, "ruff")
    if "[tool.black]" in pyproject:
        add("format", f"{py} -m black --check .", "pyproject.toml", "black")

    # Last-resort oracle: byte-compile the source.
    #
    # WHY: a repo with no test runner and no linter otherwise reports "no oracle",
    # and the method then declares every task in it undelegable. That is too
    # strict. Any repo with Python source and a working interpreter can at least
    # be compiled, and compileall EXITS NON-ZERO on a syntax error - so it is a
    # genuine oracle: it can go RED. It is deliberately weak (syntax only, never
    # behaviour), which is why it is added only when nothing stronger exists and
    # is labelled 'compile' rather than 'test'.
    #
    # This matters because the alternative is worse: given a check it cannot
    # satisfy and no sanctioned way to fail, a model will manufacture a pass.
    if interpreter and not found:
        targets = [d.name for d in root.iterdir()
                   if d.is_dir() and not is_excluded_subdir(d.name)
                   and any(d.rglob("*.py"))] if root.is_dir() else []
        has_root_py = any(root.glob("*.py"))
        if targets or has_root_py:
            scope = targets[0] if targets and not has_root_py else "."
            add("compile", f"{py} -m compileall -q {scope}",
                "fallback: Python source present, no test/lint tool configured",
                "compileall")

    return found


def detect_js_commands(root: Path) -> tuple[list[dict], str]:
    """Infer JS commands from package.json scripts and the lockfile present.

    The lockfile - not the docs, not habit - decides the package manager. Using
    npm in a pnpm repo silently produces a different dependency tree.
    """
    package_json = root / "package.json"
    if not package_json.is_file():
        return [], ""

    manager = "npm"
    for lockfile, name in (("pnpm-lock.yaml", "pnpm"), ("yarn.lock", "yarn"),
                           ("bun.lockb", "bun"), ("package-lock.json", "npm")):
        if (root / lockfile).is_file():
            manager = name
            break

    try:
        data = json.loads(read_text(package_json) or "{}")
    except json.JSONDecodeError:
        return [], manager

    scripts = data.get("scripts") or {}
    role_by_name = {
        "test": "test", "lint": "lint", "typecheck": "typecheck",
        "type-check": "typecheck", "tsc": "typecheck", "build": "build",
        "format": "format", "check": "lint",
    }
    found = []
    for name, body in scripts.items():
        role = role_by_name.get(name.lower())
        if role:
            found.append({
                "role": role,
                "command": f"{manager} run {name}",
                "evidence": f"package.json scripts.{name} -> {body}",
                "module": "",
            })
    return found, manager


def verify_commands(root: Path, commands: list[dict], interpreter: str | None,
                    deep: bool) -> None:
    """Mark each command VERIFIED / FAILED / UNVERIFIED, in place.

    Only the TOOL is invoked (--version), never the command itself. Running a
    real test suite during a probe would be slow and could mutate the repo.
    """
    for entry in commands:
        if not deep:
            entry["status"] = "UNVERIFIED"
            entry["detail"] = "not executed (use --deep)"
            continue
        module = entry.get("module")
        # The interpreter is RECORDED relative to the repo (that is what belongs
        # in FACTS.md, to be run from the repo root), but it must be INVOKED as
        # an absolute path. On Windows, subprocess resolves a relative executable
        # against the calling process's cwd, not against the `cwd=` argument - so
        # a relative interpreter silently "fails to run" and every command built
        # on it gets stamped FAILED even though it works fine.
        py = "python"
        if interpreter:
            candidate = (root / interpreter)
            py = str(candidate) if candidate.exists() else interpreter
        if module:
            ok, line = run([py, "-m", module, "--version"], root)
            if not ok:
                # Not every module answers --version; several stdlib ones
                # (compileall, py_compile, unittest) have no such flag and exit
                # non-zero. Absence of a version string is not absence of the
                # tool, so fall back to proving it is importable. Without this,
                # a perfectly good oracle is reported FAILED and the repo is
                # wrongly declared undelegable.
                ok, line = run([py, "-c", f"import {module}"], root)
                if ok:
                    line = f"importable (no --version flag)"
        else:
            head = entry["command"].split()[0]
            ok, line = run([head, "--version"], root)
        entry["status"] = "VERIFIED" if ok else "FAILED"
        entry["detail"] = line[:80] if line else (
            "tool not installed in this interpreter" if not ok else "")


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_facts(root: Path, data: dict, out: Path) -> None:
    """Write .agent/FACTS.md - the generated per-repo facts file."""
    lines: list[str] = []
    add = lines.append

    add(f"# FACTS: {root.name}")
    add("")
    add("**GENERATED FILE - do not edit by hand.** Regenerate with:")
    add("")
    add("```")
    add(f"python repo_probe.py {root} --deep")
    add("```")
    add("")
    add("Every row below was produced by inspecting this machine. Rows marked")
    add("UNVERIFIED were inferred from config files but not executed - treat them")
    add("as claims, not facts.")
    add("")

    add("## Interpreter")
    add("")
    if data["interpreters"]:
        add("| Path | Version | Status |")
        add("|---|---|---|")
        for i in data["interpreters"]:
            add(f"| `{i['path']}` | {i['version']} | {i['status']} |")
        add("")
        best = data["interpreters"][0]
        add(f"**Use this interpreter:** `{best['path']}` (Python {best['version']})")
    else:
        add("No project virtualenv found. The agent must not assume one exists.")
    add("")
    system = data["system_python"]
    add(f"_System Python is `{system['version']}` at `{system['path']}`._")
    add("_It is NOT this project's interpreter. Do not install into it._")
    add("")

    add("## Commands")
    add("")
    if data["commands"]:
        add("| Role | Command | Status | Evidence |")
        add("|---|---|---|---|")
        for c in data["commands"]:
            detail = f" - {c['detail']}" if c.get("detail") else ""
            add(f"| {c['role']} | `{c['command']}` | {c['status']}{detail} "
                f"| {c['evidence']} |")
    else:
        add("No check commands detected. **This repo has no oracle**, so no task")
        add("in it is safely delegable to an agent until one is created.")
    add("")

    verified = [c for c in data["commands"] if c["status"] == "VERIFIED"]
    add("## Closure oracle")
    add("")
    if verified:
        best = verified[0]
        add("Set the agent's stopping condition to a command from the table above:")
        add("")
        add("```")
        add(f"agent-state.sh closure \"{best['command']}\"")
        add("```")
    else:
        add("**No verified command available.** Until one exists, an agent cannot")
        add("prove it is finished, and a human owns the closure decision.")
    add("")

    if data.get("package_manager"):
        add(f"## Package manager")
        add("")
        add(f"`{data['package_manager']}` (chosen by the lockfile present, not by habit)")
        add("")

    add("## Rules that follow from the above")
    add("")
    add("1. Use the interpreter path exactly as written. Do not substitute `python`.")
    add("2. Never install into the system interpreter.")
    add("3. Never `--force-reinstall` or `--upgrade` against a system-wide")
    add("   interpreter: it deletes files before rewriting them and breaks any")
    add("   process currently using them.")
    add("4. A source build usually means no wheel exists for this Python version,")
    add("   not that a compiler is missing.")
    add("5. If a row above says UNVERIFIED or FAILED, treat the command as unproven.")
    add("   Do not report success on the strength of it.")
    add("")

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Detect and verify a repo's interpreter and check commands.")
    parser.add_argument("root", nargs="?", default=".", help="repository root")
    parser.add_argument("--deep", action="store_true",
                        help="invoke each detected tool to confirm it is installed")
    args = parser.parse_args()

    root = Path(args.root.strip()).expanduser()
    if not root.is_dir():
        print(f"error: not a directory: [{root}]", file=sys.stderr)
        return 1
    root = root.resolve()

    print(f"probing: {root}")
    interpreters = find_interpreters(root)
    # Prefer a working interpreter over one that merely exists on disk.
    interpreters.sort(key=lambda i: (i["status"] != "VERIFIED", i["path"]))
    best = interpreters[0]["path"] if interpreters else None

    commands = detect_python_commands(root, best)
    js_commands, manager = detect_js_commands(root)
    commands.extend(js_commands)
    verify_commands(root, commands, best, args.deep)

    data = {
        "root": str(root),
        "interpreters": interpreters,
        "system_python": system_python(root),
        "commands": commands,
        "package_manager": manager,
    }

    # Stamp AFTER all fields are final. The linter recomputes this and rejects a
    # mismatch, so a hand-edited facts.json fails loudly instead of passing.
    data["integrity"] = integrity_stamp(data)

    agent_dir = root / ".agent"
    agent_dir.mkdir(exist_ok=True)
    write_facts(root, data, agent_dir / "FACTS.md")
    (agent_dir / "facts.json").write_text(json.dumps(data, indent=2), encoding="utf-8")

    if best:
        print(f"  interpreter: {best} "
              f"(Python {interpreters[0]['version']}, {interpreters[0]['status']})")
    else:
        print("  interpreter: NONE FOUND")
    print(f"  system python: {data['system_python']['version']} "
          f"(recorded so it is not mistaken for the project's)")
    print(f"  commands: {len(commands)} detected"
          + ("" if args.deep else "  [UNVERIFIED - re-run with --deep to confirm]"))
    if not commands:
        print("  WARNING: no check commands found - no oracle, so nothing here is "
              "safely delegable")
    print("wrote .agent/FACTS.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
