#!/usr/bin/env python3
"""
toolchain_scan.py - Map how your repositories connect to EACH OTHER.

WHY THIS EXISTS
---------------
An import graph stops at the repository boundary. But a personal toolchain is
built out of repos that call each other, and those links are made of different
material:

    * one repo spawns another's script or executable
    * a hard-coded absolute path into a sibling repo
    * a localhost port one serves and another consumes
    * a shared data, model, or output directory

None of that appears in any import statement. All of it is plain text, which
makes it greppable - and that is the whole technique.

This is the file you want when returning to a repo months later and asking
"what did this talk to, and what breaks if I change it?"

WHAT IT DOES
------------
1. Discovers repos under a parent directory (a repo = has .git, package.json,
   pyproject.toml, requirements.txt, or a venv).
2. For each repo, records the ports it mentions and the paths it references.
3. Cross-references every repo against every OTHER repo's name and path,
   producing a directed "A references B" edge list.
4. Writes TOOLCHAIN.md next to the repos.

WHAT IT DOES NOT DO
-------------------
It proves a textual reference, not a live dependency. A path in a comment
counts the same as one in a subprocess call. Treat output as leads to confirm,
not as a verified call graph. Precision here is deliberately traded for the
ability to run on any language with no setup.

USAGE
-----
    python toolchain_scan.py <parent-dir>
    python toolchain_scan.py <parent-dir> --out TOOLCHAIN.md

Standard library only. Python 3.9+.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

# Same exclusion policy as repo_graph: never walk build output or dependencies.
SKIP_DIRS = {
    ".git", ".agent", ".idea", ".vscode", "node_modules", "__pycache__",
    "dist", "build", "out", "coverage", ".next", "target", "vendor",
    "site-packages", ".mypy_cache", ".pytest_cache", ".ruff_cache", "logs",
    "cache", ".jobs", ".assets",
}
SKIP_PREFIXES = ("venv", ".venv", "env-")

# Text files worth scanning. Binaries and lockfiles are noise.
SCAN_EXTENSIONS = {
    ".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".sh", ".bat", ".ps1",
    ".json", ".toml", ".yaml", ".yml", ".ini", ".cfg", ".md", ".txt", ".env",
}
SKIP_FILENAMES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb"}

# Cap per-file reads so one enormous generated file cannot dominate the run.
MAX_FILE_BYTES = 400_000

PORT_PATTERN = re.compile(r"(?:localhost|127\.0\.0\.1)[:/](\d{2,5})")
URL_PORT_PATTERN = re.compile(r"https?://[^\s\"'`]*:(\d{2,5})")


def is_repo(path: Path) -> bool:
    """A directory counts as a repo if it carries any project marker."""
    markers = (".git", "package.json", "pyproject.toml", "requirements.txt",
               "setup.py", "Cargo.toml", "go.mod")
    if any((path / m).exists() for m in markers):
        return True
    try:
        return any(e.is_dir() and e.name.lower().startswith(("venv", ".venv"))
                   for e in path.iterdir())
    except OSError:
        return False


def discover_repos(parent: Path) -> list[Path]:
    """Immediate subdirectories of `parent` that look like repositories."""
    repos = []
    try:
        entries = sorted(parent.iterdir())
    except OSError:
        return repos
    for entry in entries:
        if not entry.is_dir() or entry.is_symlink():
            continue
        if entry.name in SKIP_DIRS or entry.name.lower().startswith(SKIP_PREFIXES):
            continue
        if is_repo(entry):
            repos.append(entry)
    return repos


def scan_repo_text(repo: Path):
    """Yield (relative_path, text) for every scannable file in a repo."""
    stack = [repo]
    while stack:
        current = stack.pop()
        try:
            entries = list(current.iterdir())
        except OSError:
            continue
        for entry in entries:
            if entry.is_symlink():
                continue
            if entry.is_dir():
                name = entry.name
                if name in SKIP_DIRS or name.lower().startswith(SKIP_PREFIXES):
                    continue
                stack.append(entry)
            elif entry.suffix.lower() in SCAN_EXTENSIONS \
                    and entry.name not in SKIP_FILENAMES:
                try:
                    if entry.stat().st_size > MAX_FILE_BYTES:
                        continue
                    text = entry.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                yield entry.relative_to(repo).as_posix(), text


def analyse(parent: Path, repos: list[Path]) -> dict:
    """Build the cross-repo reference graph and per-repo port list."""
    # Search keys per repo: its directory name and its absolute path. Both are
    # matched case-insensitively, and both '\' and '/' forms of the path are
    # tried, because Windows source mixes the two freely.
    keys: dict[str, list[str]] = {}
    for repo in repos:
        absolute = str(repo)
        keys[repo.name] = [
            repo.name.lower(),
            absolute.lower(),
            absolute.replace("\\", "/").lower(),
        ]

    edges: dict[tuple[str, str], list[str]] = defaultdict(list)
    ports: dict[str, set[str]] = defaultdict(set)
    port_sites: dict[str, list[str]] = defaultdict(list)

    for repo in repos:
        name = repo.name
        for rel, text in scan_repo_text(repo):
            lowered = text.lower()

            for port in PORT_PATTERN.findall(text) + URL_PORT_PATTERN.findall(text):
                ports[name].add(port)
                if len(port_sites[f"{name}:{port}"]) < 3:
                    port_sites[f"{name}:{port}"].append(rel)

            for other in repos:
                if other.name == name:
                    continue
                for key in keys[other.name]:
                    # A bare directory name is only meaningful when it is long
                    # enough to be distinctive; short names produce false hits.
                    if key == other.name.lower() and len(key) < 5:
                        continue
                    if key in lowered:
                        if len(edges[(name, other.name)]) < 4:
                            edges[(name, other.name)].append(rel)
                        break

    # A shared port is a strong hint of a live producer/consumer relationship.
    shared_ports: dict[str, list[str]] = defaultdict(list)
    for repo_name, port_set in ports.items():
        for port in port_set:
            shared_ports[port].append(repo_name)
    shared_ports = {p: sorted(r) for p, r in shared_ports.items() if len(r) > 1}

    return {
        "parent": str(parent),
        "repos": [r.name for r in repos],
        "edges": {f"{a}->{b}": sites for (a, b), sites in sorted(edges.items())},
        "ports": {name: sorted(p) for name, p in sorted(ports.items()) if p},
        "shared_ports": shared_ports,
    }


def write_toolchain(data: dict, out: Path) -> None:
    lines: list[str] = []
    add = lines.append
    add("# TOOLCHAIN")
    add("")
    add(f"_Generated by toolchain_scan.py from `{data['parent']}`._")
    add("")
    add("Cross-repo links found by text reference: one repo naming another's")
    add("folder, path, or port. **These are leads, not proof** - a path in a")
    add("comment looks identical to one in a subprocess call. Confirm before")
    add("relying on any row.")
    add("")

    add(f"## Repositories ({len(data['repos'])})")
    add("")
    for name in data["repos"]:
        port_list = data["ports"].get(name)
        suffix = f" - ports: {', '.join(port_list)}" if port_list else ""
        add(f"- `{name}`{suffix}")
    add("")

    add("## References between repos")
    add("")
    if data["edges"]:
        add("| From | To | Seen in |")
        add("|---|---|---|")
        for edge, sites in data["edges"].items():
            source, target = edge.split("->")
            shown = ", ".join(f"`{s}`" for s in sites[:3])
            more = f" +{len(sites) - 3}" if len(sites) > 3 else ""
            add(f"| `{source}` | `{target}` | {shown}{more} |")
    else:
        add("None found. These repos do not mention each other by name or path.")
    add("")

    if data["shared_ports"]:
        add("## Shared ports (possible producer/consumer pairs)")
        add("")
        add("| Port | Repos |")
        add("|---|---|")
        for port, names in sorted(data["shared_ports"].items()):
            add(f"| {port} | {', '.join('`' + n + '`' for n in names)} |")
        add("")

    add("## How to use this")
    add("")
    add("1. Before changing a repo, check whether anything references it here.")
    add("2. When returning to an old repo, read its row first - it is the fastest")
    add("   reminder of what the repo was wired into.")
    add("3. Regenerate after adding or moving a repo. This file goes stale silently.")
    add("")

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Map references between sibling repositories.")
    parser.add_argument("parent", nargs="?", default=".",
                        help="directory CONTAINING your repos (not a repo itself)")
    parser.add_argument("--out", default="TOOLCHAIN.md", help="output file path")
    args = parser.parse_args()

    parent = Path(args.parent.strip()).expanduser()
    if not parent.is_dir():
        print(f"error: not a directory: [{parent}]", file=sys.stderr)
        return 1
    parent = parent.resolve()

    repos = discover_repos(parent)
    if not repos:
        print(f"no repositories found directly under {parent}", file=sys.stderr)
        print("hint: pass the directory that CONTAINS your repos", file=sys.stderr)
        return 1

    print(f"scanning {len(repos)} repo(s) under {parent}")
    data = analyse(parent, repos)

    out = Path(args.out)
    if not out.is_absolute():
        out = parent / out
    write_toolchain(data, out)

    print(f"  {len(data['edges'])} cross-repo reference(s)")
    print(f"  {len(data['shared_ports'])} shared port(s)")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
