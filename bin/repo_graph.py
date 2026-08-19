#!/usr/bin/env python3
"""
repo_graph.py - Build a dependency map of a Python / JavaScript repository.

WHY THIS EXISTS
---------------
Ranking source files by SIZE is a bad proxy for importance. A 400-line file that
every other file imports is critical infrastructure; a 600-line file that nobody
imports is an entry point. Line count cannot tell them apart.

This tool ranks by CONNECTIONS instead:

    in-degree   = how many files import this file   -> blast radius
    out-degree  = how many files this file imports  -> orchestration

That gives a four-way classification with no understanding of the code required:

    high in,  low out   -> CORE      shared infrastructure, change carefully
    low  in,  high out  -> ENTRY     start reading here
    low  in,  low out   -> LEAF      safe to edit in isolation
    zero in,  not entry -> ORPHAN    dead code... OR a dynamically loaded plugin

That last caveat is the whole reason this file is 500 lines instead of 50.
See "THE PLUGIN PROBLEM" below.

THE PLUGIN PROBLEM
------------------
Many real programs load modules by NAME at runtime, not by import statement:

    importlib.import_module('facefusion.processors.modules.' + processor + '.core')

A naive import graph gives every one of those modules an in-degree of zero and
files them as dead code - when they are in fact the core of the application.
FaceFusion loads its 12 processors, its UI layouts, its locales, and its
inference backends exactly this way.

This tool handles that in three escalating ways:

    1. It detects dynamic-loader calls and flags the calling file.
    2. When the loader argument has a constant prefix (the string concat above
       yields the prefix 'facefusion.processors.modules.'), it resolves that
       prefix against the module index and emits DYNAMIC edges to every module
       underneath. This recovers the plugin wiring automatically.
    3. It can merge a real runtime import trace (see --import-trace) which is
       ground truth and catches whatever 1 and 2 missed.

Every edge is therefore labelled with how it was learned:

    static   - a real import statement. Certain.
    dynamic  - inferred from a constant prefix on a dynamic loader. Likely.
    runtime  - observed in an actual program run. Ground truth.

An honest map that says "I don't know" beats a confident map that is wrong.

WHAT IT WRITES
--------------
    .agent/ARCHITECTURE.md  ~40 lines. The summary. Put THIS in the agent context.
    .agent/GRAPH.md         Full per-file table. Keep on disk, let the agent grep it.
    .agent/graph.json       Machine-readable, for other tools in the chain.

USAGE
-----
    python repo_graph.py <repo-root>
    python repo_graph.py <repo-root> --import-trace trace.txt
    python repo_graph.py <repo-root> --no-git

Standard library only. No pip install. Python 3.9+.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Directory names that never contain first-party source. Matched per path
# SEGMENT, never as a substring - an unanchored match would drop 'routes.ts'
# (contains 'out') and 'builder.ts' (contains 'build').
#
# 'venv*' and 'site-packages' matter more than they look: without them a Python
# repo reports its own interpreter's standard library as its largest subsystem.
EXCLUDE_DIRS = {
    ".git", ".agent", ".idea", ".vscode", ".svn", ".hg",
    "node_modules", "bower_components", "vendor",
    "dist", "build", "out", "coverage", ".next", ".nuxt", "target",
    "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".tox",
    "site-packages", ".eggs", "htmlcov", ".gradle",
}
EXCLUDE_DIR_PREFIXES = ("venv", ".venv", "env-", "virtualenv")

PY_EXTENSIONS = {".py", ".pyi"}
JS_EXTENSIONS = {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts"}

# Tried in order when a JS import omits its extension: './utils' may mean
# utils.ts, utils/index.js, and so on.
JS_RESOLVE_SUFFIXES = [
    ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts",
    "/index.ts", "/index.tsx", "/index.js", "/index.jsx", "/index.mjs",
]

# Filenames that are entry points by convention, whatever their in-degree.
ENTRY_NAMES = {
    "__main__.py", "main.py", "app.py", "cli.py", "manage.py", "run.py",
    "index.js", "index.ts", "index.mjs", "main.js", "main.ts",
    "server.js", "server.ts", "server.py",
}

# Commits touching more than this many files are almost always bulk renames,
# vendored drops, or reformat sweeps. Their co-change pairs are noise.
COCHANGE_COMMIT_LIMIT = 25


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

def is_excluded_dir(name: str) -> bool:
    """True if a directory segment should never be walked into."""
    if name in EXCLUDE_DIRS:
        return True
    lowered = name.lower()
    return any(lowered.startswith(p) for p in EXCLUDE_DIR_PREFIXES)


def load_ignore_patterns(root: Path, extra: list[str]) -> list[str]:
    """Per-repo exclusions for subsystems that are dead but still on disk.

    Reads `.agent/graph-ignore.txt` (one glob per line, '#' comments) and merges
    anything passed with --ignore.

    This is not the same as EXCLUDE_DIRS. Those are universally-not-source
    (node_modules, venv). This is "real code that this project has abandoned" -
    a retired launcher, a superseded API version, a vendored fork. Left in, dead
    subsystems distort every ranking in the map: they inflate in-degree counts,
    they dominate the git-churn column with historical noise, and they invite the
    agent to go read code that no longer matters.
    """
    patterns = list(extra)
    ignore_file = root / ".agent" / "graph-ignore.txt"
    if ignore_file.is_file():
        try:
            for line in ignore_file.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.split("#", 1)[0].strip()
                if line:
                    patterns.append(line)
        except OSError:
            pass
    return patterns


def is_ignored(rel_posix: str, patterns: list[str]) -> bool:
    """Match a repo-relative path against the ignore globs."""
    from fnmatch import fnmatch
    return any(fnmatch(rel_posix, p) or fnmatch(rel_posix, p.rstrip("/") + "/*")
               for p in patterns)


def discover_files(root: Path, ignore: list[str] | None = None) -> list[Path]:
    """Walk the repo and return every first-party Python/JS source file.

    Returns paths RELATIVE to root, using forward slashes, so that output is
    identical on Windows and Unix.
    """
    ignore = ignore or []
    found: list[Path] = []
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            entries = list(current.iterdir())
        except (PermissionError, OSError):
            # Unreadable directory - skip it rather than aborting the scan.
            continue
        for entry in entries:
            if entry.is_symlink():
                # Symlinks can point outside the repo or form cycles.
                continue
            if entry.is_dir():
                if not is_excluded_dir(entry.name):
                    stack.append(entry)
            elif entry.suffix in PY_EXTENSIONS or entry.suffix in JS_EXTENSIONS:
                rel = entry.relative_to(root)
                if not is_ignored(rel.as_posix(), ignore):
                    found.append(rel)
    return sorted(found, key=lambda p: p.as_posix())


# ---------------------------------------------------------------------------
# Python: module index and import extraction
# ---------------------------------------------------------------------------

def python_source_roots(root: Path, files: list[Path]) -> list[str]:
    """Determine which directories act as the base for absolute imports.

    Handles the two common layouts:
        flat/root layout - 'facefusion/core.py' is imported as facefusion.core
        src layout       - 'src/pkg/core.py'   is imported as pkg.core

    Returns a list of path prefixes ('' means the repo root itself).
    """
    roots = [""]
    for candidate in ("src", "lib"):
        if (root / candidate).is_dir():
            # Only treat it as a source root if it actually holds Python.
            if any(f.as_posix().startswith(candidate + "/") and f.suffix == ".py"
                   for f in files):
                roots.append(candidate + "/")
    return roots


def build_python_module_index(files: list[Path], src_roots: list[str]) -> dict[str, str]:
    """Map dotted module name -> repo-relative file path.

    'facefusion/processors/core.py'     -> facefusion.processors.core
    'facefusion/processors/__init__.py' -> facefusion.processors
    """
    index: dict[str, str] = {}
    # Two passes so that a PACKAGE always beats a same-named module. A repo with
    # both 'facefusion.py' and 'facefusion/__init__.py' is common (a launcher
    # script beside the package it launches). Getting this backwards makes the
    # launcher look like the most-imported file in the project - it absorbs every
    # 'from facefusion.x import y' that walks up to the bare name 'facefusion'.
    for is_package_pass in (False, True):
        for f in files:
            if f.suffix not in PY_EXTENSIONS:
                continue
            is_init = f.name.startswith("__init__.")
            if is_init != is_package_pass:
                continue
            posix = f.as_posix()
            for src_root in src_roots:
                if src_root and not posix.startswith(src_root):
                    continue
                relative = posix[len(src_root):]
                parts = relative[:-len(f.suffix)].split("/")
                if parts[-1] == "__init__":
                    parts = parts[:-1]
                if not parts:
                    continue
                dotted = ".".join(parts)
                if is_package_pass:
                    index[dotted] = posix       # package wins outright
                else:
                    index.setdefault(dotted, posix)
    return index


def _constant_prefix(node: ast.AST) -> str | None:
    """Recover the fixed leading text of a dynamically built module string.

    This is what makes plugin discovery work. Given:

        importlib.import_module('facefusion.processors.modules.' + name + '.core')

    the argument is a BinOp tree whose leftmost leaf is the constant
    'facefusion.processors.modules.'. Returning that prefix lets the caller
    match every module underneath it.

    Handles string concatenation, f-strings, and .format() calls.
    Returns None when there is no usable constant head.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        # Recurse left: 'a.b.' + x + '.c' nests as ((('a.b.' + x) + '.c')
        return _constant_prefix(node.left)
    if isinstance(node, ast.JoinedStr):  # f-string
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                return value.value
            break  # only a leading literal counts
        return None
    if isinstance(node, ast.Call):
        # 'pkg.{}.core'.format(name)  -> take the format string's head
        if isinstance(node.func, ast.Attribute) and node.func.attr == "format":
            if isinstance(node.func.value, ast.Constant):
                text = node.func.value.value
                if isinstance(text, str):
                    return text.split("{")[0]
    return None


def parse_python_file(path: Path, rel: str, package_parts: list[str]):
    """Extract imports and dynamic-loader calls from one Python file.

    Returns (static_targets, dynamic_prefixes, has_loader, parse_failed).

    `has_loader` is tracked SEPARATELY from `dynamic_prefixes` on purpose. A file
    calling importlib with a fully variable argument yields no prefix, so it
    contributes no edges - but it is precisely the file where the graph is most
    blind, and it must still be reported. Reporting only the resolvable cases
    would hide the unresolvable ones, which is backwards.
    """
    static: list[str] = []
    dynamic: list[str] = []
    has_loader = False
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=rel)
    except (SyntaxError, ValueError, OSError):
        # A file we cannot parse is reported rather than silently dropped -
        # a missing file would otherwise look like a file with no dependencies.
        return static, dynamic, has_loader, True

    for node in ast.walk(tree):
        # ---- plain imports:  import a.b.c
        if isinstance(node, ast.Import):
            for alias in node.names:
                static.append(alias.name)

        # ---- from imports:  from a.b import c   /   from . import c
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                # Relative import. level=1 is the containing package,
                # level=2 its parent, and so on.
                base = package_parts[:len(package_parts) - (node.level - 1)] \
                    if node.level - 1 <= len(package_parts) else []
                prefix = ".".join(base)
            else:
                prefix = ""
            module = node.module or ""
            head = ".".join(p for p in (prefix, module) if p)
            if head:
                static.append(head)
            # 'from pkg import submodule' may name a MODULE rather than a symbol,
            # so record both possibilities and let the resolver pick.
            for alias in node.names:
                if alias.name != "*":
                    static.append(".".join(p for p in (head, alias.name) if p))

        # ---- dynamic loaders:  importlib.import_module(...) / __import__(...)
        elif isinstance(node, ast.Call):
            func = node.func
            is_loader = (
                (isinstance(func, ast.Attribute) and func.attr in ("import_module", "__import__"))
                or (isinstance(func, ast.Name) and func.id == "__import__")
            )
            if is_loader and node.args:
                has_loader = True
                prefix = _constant_prefix(node.args[0])
                if prefix:
                    dynamic.append(prefix)

    return static, dynamic, has_loader, False


def resolve_python_target(dotted: str, index: dict[str, str]) -> str | None:
    """Map a dotted import to a repo file, walking up to the nearest package.

    'facefusion.processors.core.SOME_CONST' resolves to the module
    'facefusion.processors.core' once the trailing symbol is trimmed.
    Anything that never matches is third-party or stdlib, and is dropped.
    """
    parts = dotted.split(".")
    while parts:
        candidate = ".".join(parts)
        if candidate in index:
            return index[candidate]
        parts.pop()
    return None


# ---------------------------------------------------------------------------
# JavaScript / TypeScript: import extraction
# ---------------------------------------------------------------------------

# Deliberately regex-based rather than a full JS parser: it handles the four
# real-world forms and needs no dependency. Anything it misses shows up as a
# missing edge, never as a wrong one.
JS_IMPORT_PATTERNS = [
    re.compile(r"""\bfrom\s+['"]([^'"]+)['"]"""),          # import x from './y'
    re.compile(r"""\bimport\s+['"]([^'"]+)['"]"""),        # import './y'
    re.compile(r"""\brequire\s*\(\s*['"]([^'"]+)['"]"""),  # require('./y')
    re.compile(r"""\bimport\s*\(\s*['"]([^'"]+)['"]"""),   # await import('./y')
]

# A require()/import() whose argument is NOT a plain string is a dynamic load.
JS_DYNAMIC_PATTERNS = [
    re.compile(r"""\brequire\s*\(\s*[^'")\s]"""),
    re.compile(r"""\bimport\s*\(\s*[^'")\s]"""),
]


def load_js_aliases(root: Path) -> dict[str, str]:
    """Read tsconfig/jsconfig path aliases so '@/utils' resolves correctly.

    Without this, aliased imports look like third-party packages and their
    edges vanish from the graph.
    """
    aliases: dict[str, str] = {}
    for name in ("tsconfig.json", "jsconfig.json"):
        config_path = root / name
        if not config_path.is_file():
            continue
        try:
            text = config_path.read_text(encoding="utf-8", errors="replace")
            # tsconfig routinely contains comments and trailing commas, which
            # strict JSON rejects. Strip the common cases before parsing.
            text = re.sub(r"//[^\n]*", "", text)
            text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
            text = re.sub(r",(\s*[}\]])", r"\1", text)
            data = json.loads(text)
        except (json.JSONDecodeError, OSError):
            continue
        options = data.get("compilerOptions", {}) or {}
        base_url = (options.get("baseUrl") or ".").strip("./")
        for pattern, targets in (options.get("paths") or {}).items():
            if not targets:
                continue
            key = pattern.replace("/*", "").replace("*", "")
            value = str(targets[0]).replace("/*", "").replace("*", "")
            prefix = f"{base_url}/" if base_url else ""
            aliases[key] = (prefix + value).strip("/")
    return aliases


def resolve_js_target(spec: str, importer: Path, root: Path,
                      known: set[str], aliases: dict[str, str]) -> str | None:
    """Resolve a JS import specifier to a repo file, or None if external.

    Bare specifiers ('react', 'lodash') are npm packages, not internal edges,
    and are dropped - counting them would drown the graph.
    """
    if spec.startswith("."):
        base = (importer.parent / spec).as_posix()
        # Normalise '../' segments without touching the filesystem.
        parts: list[str] = []
        for segment in base.split("/"):
            if segment in ("", "."):
                continue
            if segment == "..":
                if parts:
                    parts.pop()
            else:
                parts.append(segment)
        base = "/".join(parts)
    else:
        matched = None
        for key, target in aliases.items():
            if key and spec.startswith(key):
                matched = target + spec[len(key):]
                break
        if matched is None:
            return None  # third-party package
        base = matched.strip("/")

    if base in known:
        return base
    for suffix in JS_RESOLVE_SUFFIXES:
        candidate = base + suffix
        if candidate in known:
            return candidate
    return None


# ---------------------------------------------------------------------------
# Git signals: churn and co-change coupling
# ---------------------------------------------------------------------------

def git_history(root: Path):
    """Return (churn, cochange) from git log, or empty results if unavailable.

    churn    - how many commits touched each file. High churn marks where the
               real work happens, which import counts alone never reveal.
    cochange - how often two files changed in the SAME commit. This catches
               coupling that no import expresses: a config file and the module
               that reads it, a schema and its migration.
    """
    churn: Counter[str] = Counter()
    cochange: Counter[tuple[str, str]] = Counter()
    try:
        result = subprocess.run(
            ["git", "log", "--format=%H", "--name-only", "--no-merges"],
            cwd=root, capture_output=True, text=True, timeout=120,
        )
    except (OSError, subprocess.SubprocessError):
        return churn, cochange
    if result.returncode != 0:
        return churn, cochange

    commit_files: list[str] = []

    def flush(batch: list[str]) -> None:
        for f in batch:
            churn[f] += 1
        if 1 < len(batch) <= COCHANGE_COMMIT_LIMIT:
            ordered = sorted(set(batch))
            for i, a in enumerate(ordered):
                for b in ordered[i + 1:]:
                    cochange[(a, b)] += 1

    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        # A 40-char hex line starts a new commit block.
        if len(line) == 40 and all(c in "0123456789abcdef" for c in line):
            flush(commit_files)
            commit_files = []
        else:
            commit_files.append(line)
    flush(commit_files)
    return churn, cochange


# ---------------------------------------------------------------------------
# Runtime trace merge (ground truth)
# ---------------------------------------------------------------------------

def parse_import_trace(trace_path: Path, index: dict[str, str]):
    """Parse `python -X importtime` output into real import edges.

    Ground truth: whatever the program ACTUALLY loaded, including everything
    the static and prefix passes missed. Produce it with:

        python -X importtime your_entry.py 2> trace.txt

    The importtime format indents nested imports, so column depth reconstructs
    who imported whom:

        import time:  123 | 456 |   facefusion.processors.core
                                  ^^ two spaces deeper == imported by the line above
    """
    edges: set[tuple[str, str]] = set()
    loaded: set[str] = set()
    stack: list[tuple[int, str]] = []  # (indent depth, file path)

    try:
        lines = trace_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return edges, loaded

    for line in lines:
        if "|" not in line or not line.startswith("import time"):
            continue
        module_field = line.rsplit("|", 1)[-1]
        module = module_field.strip()
        if not module:
            continue
        indent = len(module_field) - len(module_field.lstrip())
        path = index.get(module)
        if path:
            loaded.add(path)
        # Maintain the ancestry stack by indentation depth.
        while stack and stack[-1][0] >= indent:
            stack.pop()
        if path:
            if stack:
                parent = stack[-1][1]
                if parent != path:
                    edges.add((parent, path))
            stack.append((indent, path))
    return edges, loaded


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def is_test_file(path: str) -> bool:
    """Tests are never imported by anything - that is normal, not dead code.

    Without this they dominate the 'unreferenced' list and train the reader to
    ignore it, which destroys the one signal that actually finds dead code.
    """
    name = path.rsplit("/", 1)[-1]
    first = path.split("/")[0]
    return (
        first in ("tests", "test", "__tests__", "spec")
        or name.startswith("test_")
        or name.endswith(("_test.py", ".test.js", ".test.ts", ".spec.js", ".spec.ts"))
    )


def classify(path: str, in_deg: int, out_deg: int, core_cut: int,
             dynamic_loaded: bool, runtime_loaded: bool,
             static_in_deg: int = 0) -> str:
    """Assign one architectural role per file. Order of checks matters."""
    name = path.rsplit("/", 1)[-1]
    depth = path.count("/")
    if is_test_file(path):
        return "TEST"
    # Nothing imports this in source, yet it IS loaded - a plugin, and the most
    # important thing this map can tell a reader who would otherwise delete it.
    if static_in_deg == 0 and not name.startswith("__init__."):
        if runtime_loaded:
            return "RUNTIME-LOADED"
        if dynamic_loaded:
            return "PLUGIN"
    if in_deg == 0:
        # Never claim 'dead' for something we know is loaded another way.
        if runtime_loaded:
            return "RUNTIME-LOADED"
        if dynamic_loaded:
            return "PLUGIN"
        # A package marker is imported implicitly by importing the package.
        if name.startswith("__init__."):
            return "PACKAGE"
        if name in ENTRY_NAMES or depth == 0:
            return "ENTRY"
        return "ORPHAN?"
    if in_deg >= core_cut and out_deg <= in_deg:
        return "CORE"
    if out_deg > in_deg * 2 and out_deg >= 3:
        return "ORCHESTRATOR"
    return "LEAF"


def directory_of(path: str, depth: int = 2) -> str:
    """Group key for a file: its directory, capped at `depth` segments."""
    parts = path.split("/")
    if len(parts) == 1:
        return "(root)"
    return "/".join(parts[:min(depth, len(parts) - 1)])


def analyse(root: Path, use_git: bool, trace_path: Path | None,
            ignore: list[str] | None = None) -> dict:
    """Run the whole pipeline and return a single result dictionary."""
    ignore = ignore or []
    files = discover_files(root, ignore)
    known = {f.as_posix() for f in files}
    src_roots = python_source_roots(root, files)
    py_index = build_python_module_index(files, src_roots)
    js_aliases = load_js_aliases(root)

    # edges[(src, dst)] = how the edge was learned
    edges: dict[tuple[str, str], str] = {}
    dynamic_loader_files: list[str] = []
    unparsed: list[str] = []
    plugin_targets: set[str] = set()

    for rel_path in files:
        rel = rel_path.as_posix()
        full = root / rel_path

        if rel_path.suffix in PY_EXTENSIONS:
            # The file's own package, needed to resolve relative imports.
            module_name = next(
                (m for m, p in py_index.items() if p == rel), ""
            )
            package_parts = module_name.split(".")[:-1] if module_name else []

            static, dyn_prefixes, has_loader, failed = parse_python_file(
                full, rel, package_parts)
            if failed:
                unparsed.append(rel)
                continue
            if has_loader:
                dynamic_loader_files.append(rel)

            for dotted in static:
                target = resolve_python_target(dotted, py_index)
                if target and target != rel:
                    edges.setdefault((rel, target), "static")

            if dyn_prefixes:
                for prefix in dyn_prefixes:
                    # Match every known module sitting under the constant head.
                    # This is what recovers plugin wiring like
                    # 'facefusion.processors.modules.' -> all 12 processors.
                    if "." not in prefix:
                        continue
                    for module, target in py_index.items():
                        if module.startswith(prefix) and target != rel:
                            edges.setdefault((rel, target), "dynamic")
                            plugin_targets.add(target)

        else:  # JavaScript / TypeScript
            try:
                text = full.read_text(encoding="utf-8", errors="replace")
            except OSError:
                unparsed.append(rel)
                continue
            for pattern in JS_IMPORT_PATTERNS:
                for spec in pattern.findall(text):
                    target = resolve_js_target(spec, rel_path, root, known, js_aliases)
                    if target and target != rel:
                        edges.setdefault((rel, target), "static")
            if any(p.search(text) for p in JS_DYNAMIC_PATTERNS):
                dynamic_loader_files.append(rel)

    # ---- merge the runtime trace, which overrides guesses with observations
    runtime_loaded: set[str] = set()
    if trace_path and trace_path.is_file():
        runtime_edges, runtime_loaded = parse_import_trace(trace_path, py_index)
        for edge in runtime_edges:
            edges[edge] = "runtime"

    # ---- degrees
    #
    # Static in-degree is tracked separately from total. A plugin's ONLY inbound
    # edges are the dynamic ones this tool inferred, so judging by total
    # in-degree would hide it among ordinary leaves - the inferred edge is
    # exactly what stops it looking like a plugin. "No import statement anywhere
    # points at this, but something loads it by name" is the signal worth
    # surfacing, and it needs the static count to detect.
    in_deg: Counter[str] = Counter()
    out_deg: Counter[str] = Counter()
    static_in_deg: Counter[str] = Counter()
    for (src, dst), kind in edges.items():
        out_deg[src] += 1
        in_deg[dst] += 1
        if kind == "static":
            static_in_deg[dst] += 1

    # 'CORE' should mean genuinely well-connected, not merely non-zero. Use the
    # 80th percentile of non-zero in-degrees so the cut adapts to repo size.
    nonzero = sorted(v for v in in_deg.values() if v > 0)
    core_cut = nonzero[int(len(nonzero) * 0.8)] if nonzero else 1
    core_cut = max(core_cut, 2)

    churn, cochange = git_history(root) if use_git else (Counter(), Counter())

    # How much of the source is actually under version control? A checkout where
    # the app was dropped in as untracked files (or is mostly gitignored) yields
    # a churn column of all zeros. That is a MISSING SIGNAL, not "nothing ever
    # changed" - and the map has to say which, or the reader draws the wrong
    # conclusion from a table full of honest-looking zeros.
    tracked: set[str] = set()
    if use_git:
        try:
            listed = subprocess.run(["git", "ls-files"], cwd=root,
                                    capture_output=True, text=True, timeout=60)
            if listed.returncode == 0:
                tracked = {line.strip() for line in listed.stdout.splitlines() if line.strip()}
        except (OSError, subprocess.SubprocessError):
            pass
    graph_files = {f.as_posix() for f in files}
    tracked_in_graph = len(graph_files & tracked)
    git_coverage = round(tracked_in_graph / len(graph_files), 2) if graph_files else 0.0

    records = []
    for rel_path in files:
        rel = rel_path.as_posix()
        records.append({
            "path": rel,
            "in": in_deg.get(rel, 0),
            "out": out_deg.get(rel, 0),
            "churn": churn.get(rel, 0),
            "role": classify(rel, in_deg.get(rel, 0), out_deg.get(rel, 0),
                             core_cut, rel in plugin_targets, rel in runtime_loaded,
                             static_in_deg.get(rel, 0)),
            "dir": directory_of(rel),
        })

    # ---- cluster cohesion: does the folder structure match the real wiring?
    #
    # Folders are the primary grouping because in most repos the developers
    # already did the clustering for you. The graph's job is to CHECK that,
    # and the disagreements are the valuable output.
    dir_files: dict[str, list[str]] = defaultdict(list)
    for record in records:
        dir_files[record["dir"]].append(record["path"])

    clusters = []
    for name, members in sorted(dir_files.items()):
        member_set = set(members)
        internal = external = 0
        for (src, dst) in edges:
            src_in, dst_in = src in member_set, dst in member_set
            if src_in and dst_in:
                internal += 1
            elif src_in or dst_in:
                external += 1
        total = internal + external
        clusters.append({
            "name": name,
            "files": len(members),
            "internal_edges": internal,
            "external_edges": external,
            # 1.0 = fully self-contained subsystem, 0.0 = not a real grouping
            "cohesion": round(internal / total, 2) if total else 0.0,
        })
    clusters.sort(key=lambda c: -c["files"])

    # ---- misfits: files wired mostly to a directory other than their own
    misfits = []
    for record in records:
        rel = record["path"]
        if record["in"] + record["out"] == 0:
            continue
        # Entry points and tests point at the code they drive BY DESIGN. Flagging
        # them as misfiled is guaranteed noise, and noise here is expensive: this
        # section is only useful if every row is worth a human look.
        if record["role"] in ("ENTRY", "TEST", "PACKAGE"):
            continue
        neighbour_dirs: Counter[str] = Counter()
        for (src, dst) in edges:
            if src == rel:
                neighbour_dirs[directory_of(dst)] += 1
            elif dst == rel:
                neighbour_dirs[directory_of(src)] += 1
        if not neighbour_dirs:
            continue
        top_dir, top_count = neighbour_dirs.most_common(1)[0]
        total = sum(neighbour_dirs.values())
        # A file leaning on its own PARENT directory is ordinary layering -
        # 'app/ui/widgets/x.py' depending on 'app' is how layered code is meant
        # to look. Only a pull toward an unrelated PEER directory is evidence of
        # misfiling. Without this the section fires on nearly every leaf file in
        # any layered codebase and becomes unreadable.
        related = (top_dir.startswith(record["dir"] + "/")
                   or record["dir"].startswith(top_dir + "/"))
        if (top_dir != record["dir"] and not related
                and top_count / total >= 0.6 and total >= 3):
            misfits.append({
                "path": rel, "sits_in": record["dir"],
                "belongs_with": top_dir,
                "ratio": round(top_count / total, 2),
            })
    misfits.sort(key=lambda m: -m["ratio"])

    top_cochange = [
        {"a": a, "b": b, "count": n}
        for (a, b), n in cochange.most_common(15) if n >= 3
    ]

    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=root,
                             capture_output=True, text=True, timeout=15).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        sha = ""

    return {
        "root": str(root),
        "git_sha": sha or "(not a git repo)",
        "git_coverage": git_coverage,
        "git_tracked_in_graph": tracked_in_graph,
        "ignored_patterns": ignore,
        "file_count": len(files),
        "edge_count": len(edges),
        "edge_kinds": dict(Counter(edges.values())),
        "core_cut": core_cut,
        "records": records,
        "clusters": clusters,
        "misfits": misfits,
        "dynamic_loader_files": sorted(set(dynamic_loader_files)),
        "plugin_targets": sorted(plugin_targets),
        "runtime_loaded": sorted(runtime_loaded),
        "unparsed": unparsed,
        "cochange": top_cochange,
        "trace_used": bool(trace_path and trace_path.is_file()),
    }


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_architecture(data: dict, out: Path) -> None:
    """The SMALL file. This is the one that goes into the agent's context.

    Kept near 40 lines on purpose: a long map defeats its own purpose, because
    retrieval accuracy falls as context grows - and falls hardest on the small
    local models this is written for.
    """
    lines: list[str] = []
    add = lines.append
    add("# ARCHITECTURE")
    add("")
    add(f"_Generated by repo_graph.py at commit `{data['git_sha']}`. "
        f"{data['file_count']} source files, {data['edge_count']} dependencies._")
    add("")
    add("If the commit above is not HEAD, this map is stale - regenerate before trusting it.")
    add("")

    entries = [r for r in data["records"] if r["role"] == "ENTRY"]
    if entries:
        add("## Start here (entry points)")
        add("")
        for r in sorted(entries, key=lambda r: -r["out"])[:8]:
            add(f"- `{r['path']}` (imports {r['out']} files)")
        add("")

    core = sorted([r for r in data["records"] if r["role"] == "CORE"],
                  key=lambda r: -r["in"])[:10]
    if core:
        add("## Core - highest blast radius, change carefully")
        add("")
        add("| File | Imported by | Commits |")
        add("|---|---:|---:|")
        for r in core:
            add(f"| `{r['path']}` | {r['in']} | {r['churn']} |")
        add("")

    real_clusters = [c for c in data["clusters"] if c["files"] >= 3][:10]
    if real_clusters:
        add("## Subsystems")
        add("")
        add("Folders are the grouping; cohesion measures whether the folder is honest.")
        add("Compare groups against EACH OTHER, not against 1.0 - in a healthy layered")
        add("codebase every group leans on shared core, so real subsystems commonly sit")
        add("around 0.2-0.4. A group near 0.0 is a bucket of unrelated files.")
        add("")
        add("| Group | Files | Cohesion | AI: what is this? |")
        add("|---|---:|---:|---|")
        for c in real_clusters:
            add(f"| `{c['name']}` | {c['files']} | {c['cohesion']} | _(unlabelled)_ |")
        add("")

    plugins = [r for r in data["records"] if r["role"] in ("PLUGIN", "RUNTIME-LOADED")]
    if plugins:
        add("## Loaded dynamically - NOT dead code")
        add("")
        add(f"{len(plugins)} files are loaded by name at runtime, not by import "
            "statement. A naive import graph would call these dead. They are not.")
        add("")
        for r in plugins[:6]:
            add(f"- `{r['path']}`")
        if len(plugins) > 6:
            add(f"- _...and {len(plugins) - 6} more (see GRAPH.md)_")
        add("")

    if data["misfits"]:
        add("## Possibly misfiled")
        add("")
        for m in data["misfits"][:5]:
            add(f"- `{m['path']}` sits in `{m['sits_in']}` but "
                f"{int(m['ratio'] * 100)}% of its links go to `{m['belongs_with']}`")
        add("")

    orphans = [r for r in data["records"] if r["role"] == "ORPHAN?"]
    if orphans:
        add(f"## Unreferenced ({len(orphans)})")
        add("")
        add("Nothing imports these and they are not entry points. Candidates for "
            "dead code - but confirm with a runtime trace before deleting.")
        add("")
        for r in orphans[:6]:
            add(f"- `{r['path']}`")
        add("")

    add("## Confidence")
    add("")
    kinds = data["edge_kinds"]
    add(f"- static (certain): {kinds.get('static', 0)}")
    add(f"- dynamic (inferred from a name prefix): {kinds.get('dynamic', 0)}")
    add(f"- runtime (observed in a real run): {kinds.get('runtime', 0)}")
    if not data["trace_used"]:
        add("")
        add("**No runtime trace was merged.** Dynamic wiring is inferred, not observed. "
            "For ground truth run the app once with `-X importtime` and pass "
            "`--import-trace` (see MANUAL.md step 4).")
    if data["git_coverage"] < 0.5:
        add("")
        add(f"- **The Commits column is unusable here.** Only "
            f"{int(data['git_coverage'] * 100)}% of these files are git-tracked "
            f"({data['git_tracked_in_graph']} of {data['file_count']}), so a zero means "
            "'not in version control', NOT 'never changed'. Ignore churn in this repo.")
    if data["ignored_patterns"]:
        add("")
        add(f"- Excluded by `.agent/graph-ignore.txt`: "
            f"{', '.join('`' + p + '`' for p in data['ignored_patterns'])}")
    if data["unparsed"]:
        add("")
        add(f"- **{len(data['unparsed'])} file(s) could not be parsed** and are missing "
            "from the graph entirely. See GRAPH.md.")
    add("")

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_graph(data: dict, out: Path) -> None:
    """The BIG file. Stays on disk; the agent greps it instead of reading it."""
    lines: list[str] = []
    add = lines.append
    add("# GRAPH - full dependency table")
    add("")
    add(f"_Commit `{data['git_sha']}`. Do not read this whole file - grep it._")
    add("")
    add("Roles: CORE (many importers) | ENTRY (start here) | ORCHESTRATOR (imports many) |")
    add("LEAF (isolated) | PLUGIN (loaded by name) | RUNTIME-LOADED (observed) | ORPHAN? (unreferenced)")
    add("")
    add("| File | Role | In | Out | Commits | Group |")
    add("|---|---|---:|---:|---:|---|")
    ordered = sorted(data["records"], key=lambda r: (-r["in"], -r["churn"], r["path"]))
    for r in ordered:
        add(f"| `{r['path']}` | {r['role']} | {r['in']} | {r['out']} | "
            f"{r['churn']} | `{r['dir']}` |")
    add("")

    if data["dynamic_loader_files"]:
        add("## Files that load modules by name")
        add("")
        add("The graph is incomplete around these. They decide at runtime what to import.")
        add("")
        for f in data["dynamic_loader_files"]:
            add(f"- `{f}`")
        add("")

    if data["cochange"]:
        add("## Coupled by history (changed together in the same commit)")
        add("")
        add("These links exist even when no import connects the files.")
        add("")
        add("| File A | File B | Commits together |")
        add("|---|---|---:|")
        for c in data["cochange"]:
            add(f"| `{c['a']}` | `{c['b']}` | {c['count']} |")
        add("")

    if data["unparsed"]:
        add("## Could not parse (absent from the graph)")
        add("")
        for f in data["unparsed"]:
            add(f"- `{f}`")
        add("")

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a dependency map of a Python/JS repo.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Writes .agent/ARCHITECTURE.md, .agent/GRAPH.md and .agent/graph.json",
    )
    parser.add_argument("root", nargs="?", default=".", help="repository root")
    parser.add_argument("--import-trace", metavar="FILE",
                        help="output of `python -X importtime <entry>` for ground truth")
    parser.add_argument("--no-git", action="store_true",
                        help="skip git churn and co-change analysis")
    parser.add_argument("--ignore", action="append", default=[], metavar="GLOB",
                        help="exclude a dead subsystem, e.g. --ignore 'legacy/*' "
                             "(repeatable; also read from .agent/graph-ignore.txt)")
    args = parser.parse_args()

    # Strip stray whitespace: a copy-pasted ' D:\repo' is invisible otherwise.
    root = Path(args.root.strip()).expanduser()
    if not root.is_dir():
        print(f"error: not a directory: [{root}]", file=sys.stderr)
        return 1
    root = root.resolve()

    trace = Path(args.import_trace.strip()).expanduser() if args.import_trace else None
    if trace and not trace.is_file():
        print(f"warning: trace file not found, continuing without it: [{trace}]",
              file=sys.stderr)
        trace = None

    ignore = load_ignore_patterns(root, args.ignore)
    print(f"scanning: {root}")
    if ignore:
        print(f"  ignoring: {', '.join(ignore)}")
    data = analyse(root, use_git=not args.no_git, trace_path=trace, ignore=ignore)

    agent_dir = root / ".agent"
    agent_dir.mkdir(exist_ok=True)
    write_architecture(data, agent_dir / "ARCHITECTURE.md")
    write_graph(data, agent_dir / "GRAPH.md")
    (agent_dir / "graph.json").write_text(
        json.dumps(data, indent=2), encoding="utf-8")

    print(f"  {data['file_count']} files, {data['edge_count']} dependencies "
          f"({data['edge_kinds']})")
    if data["dynamic_loader_files"]:
        print(f"  {len(data['dynamic_loader_files'])} file(s) load modules by name; "
              f"{len(data['plugin_targets'])} plugin target(s) recovered")
    if data["unparsed"]:
        print(f"  WARNING: {len(data['unparsed'])} file(s) failed to parse")
    if not data["trace_used"]:
        print("  NOTE: no runtime trace merged - dynamic wiring is inferred, not observed")
    print("wrote .agent/ARCHITECTURE.md  <- put this in the agent context")
    print("wrote .agent/GRAPH.md         <- leave on disk, let the agent grep it")
    print("wrote .agent/graph.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
