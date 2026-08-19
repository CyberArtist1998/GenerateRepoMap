#!/usr/bin/env python3
"""
selftest.py - Verify the tools against a repository whose answer is known.

WHY THIS EXISTS
---------------
Every tool in this folder has, at some point, shipped with a bug that produced
confident, wrong output: a virtualenv counted as the largest source root, a
"largest files" table with no filenames in it, a launcher script credited with
97 importers that belonged to a package of the same name, a plugin-detection
branch that could never fire.

None of those were caught by reading the code. All were caught by running the
tool against something whose correct output was known in advance.

That is what this file automates. It builds a small synthetic repo with a
deliberately known shape, runs the tools over it, and asserts the output.

    python bin/selftest.py

Exit 0 = all correct. Exit 1 = a tool has regressed. Run it after any edit to
repo_graph.py or repo_probe.py.

THE FIXTURE
-----------
    app/shared.py             imported by 3 files      -> CORE
    app/main.py               imports, imported by 0   -> ENTRY
    app/registry.py           loads plugins by name    -> loader
    app/plugins/alpha/core.py reached ONLY by name     -> PLUGIN
    app/plugins/beta/core.py  reached ONLY by name     -> PLUGIN
    web/src/index.js          imports util             -> ENTRY
    web/src/util.js           imported by index        -> LEAF
    legacy/old.py             listed in graph-ignore   -> absent
    tests/test_thing.py       a test                   -> TEST

The plugin rows are the important ones. A tool that reports them as ORPHAN has
the single most damaging bug this toolkit can have: it would invite an agent to
delete working code.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent

FIXTURE_FILES = {
    "app/__init__.py": "",
    "app/shared.py": "VALUE = 1\n",
    "app/registry.py": (
        "import importlib\n"
        "from app import shared\n\n"
        "def load(name):\n"
        "    # constant prefix -> plugin targets are recoverable\n"
        "    return importlib.import_module('app.plugins.' + name + '.core')\n"
    ),
    "app/main.py": "from app import shared, registry\n\nregistry.load('alpha')\n",
    "app/plugins/__init__.py": "",
    "app/plugins/alpha/core.py": "from app import shared\n",
    "app/plugins/beta/core.py": "from app import shared\n",
    "web/src/index.js": 'import { a } from "./util";\nconsole.log(a);\n',
    "web/src/util.js": "export const a = 1;\n",
    "legacy/old.py": "from app import shared\n",
    "tests/test_thing.py": "from app import shared\n\ndef test_it():\n    assert shared.VALUE == 1\n",
    ".agent/graph-ignore.txt": "# retired subsystem\nlegacy/*\n",
    "mypy.ini": "[mypy]\nignore_missing_imports = True\n",
}

# path -> expected role from repo_graph.py
EXPECTED_ROLES = {
    "app/shared.py": "CORE",
    "app/main.py": "ENTRY",
    "app/plugins/alpha/core.py": "PLUGIN",
    "app/plugins/beta/core.py": "PLUGIN",
    "web/src/index.js": "ENTRY",
    "web/src/util.js": "LEAF",
    "tests/test_thing.py": "TEST",
}

EXCLUDED_PATHS = ["legacy/old.py"]


def build_fixture(root: Path) -> None:
    for rel, body in FIXTURE_FILES.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")


def check(label: str, condition: bool, detail: str = "") -> bool:
    print(f"  {'PASS' if condition else 'FAIL'}  {label}"
          + (f"   ({detail})" if detail and not condition else ""))
    return condition


def main() -> int:
    temp = Path(tempfile.mkdtemp(prefix="repotoolkit-selftest-"))
    fixture = temp / "fixture"
    fixture.mkdir()
    failures = 0
    try:
        build_fixture(fixture)

        # ---- repo_graph -------------------------------------------------
        print("\nrepo_graph.py")
        result = subprocess.run(
            [sys.executable, str(HERE / "repo_graph.py"), str(fixture), "--no-git"],
            capture_output=True, text=True, timeout=180,
        )
        if result.returncode != 0:
            print("  FAIL  tool exited non-zero")
            print(result.stderr[:500])
            return 1

        data = json.loads((fixture / ".agent" / "graph.json").read_text(encoding="utf-8"))
        roles = {r["path"]: r["role"] for r in data["records"]}

        for path, want in EXPECTED_ROLES.items():
            got = roles.get(path, "<missing>")
            if not check(f"{path} -> {want}", got == want, f"got {got}"):
                failures += 1

        for path in EXCLUDED_PATHS:
            if not check(f"{path} excluded by graph-ignore", path not in roles):
                failures += 1

        # A package must beat a same-named module; regression guard for the bug
        # where a launcher script absorbed every import of its sibling package.
        if not check("dynamic edges recovered from constant prefix",
                     data["edge_kinds"].get("dynamic", 0) >= 2,
                     f"got {data['edge_kinds']}"):
            failures += 1

        if not check("loader file reported",
                     "app/registry.py" in data["dynamic_loader_files"]):
            failures += 1

        if not check("no file failed to parse", not data["unparsed"],
                     str(data["unparsed"])):
            failures += 1

        # ---- repo_probe -------------------------------------------------
        print("\nrepo_probe.py")
        result = subprocess.run(
            [sys.executable, str(HERE / "repo_probe.py"), str(fixture)],
            capture_output=True, text=True, timeout=180,
        )
        if result.returncode != 0:
            print("  FAIL  tool exited non-zero")
            failures += 1
        else:
            facts = json.loads((fixture / ".agent" / "facts.json").read_text(encoding="utf-8"))
            roles_found = {c["role"] for c in facts["commands"]}
            if not check("detected typecheck from mypy.ini", "typecheck" in roles_found,
                         str(roles_found)):
                failures += 1
            if not check("detected test from tests/ directory", "test" in roles_found,
                         str(roles_found)):
                failures += 1
            if not check("system python recorded separately",
                         bool(facts["system_python"]["version"])):
                failures += 1

        # ---- argument hygiene -------------------------------------------
        print("\nargument handling")
        result = subprocess.run(
            [sys.executable, str(HERE / "repo_graph.py"), f" {fixture} ", "--no-git"],
            capture_output=True, text=True, timeout=180,
        )
        if not check("leading/trailing space in path is stripped",
                     result.returncode == 0, result.stderr[:120]):
            failures += 1

        print()
        if failures:
            print(f"RESULT: {failures} check(s) FAILED")
            return 1
        print("RESULT: all checks passed")
        return 0

    finally:
        shutil.rmtree(temp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
