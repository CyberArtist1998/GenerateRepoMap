#!/usr/bin/env python3
"""
lint_agent_files.py - An oracle for the instruction files themselves.

WHY THIS EXISTS
---------------
The whole method insists that every task carry a mechanical check. The
instruction files carrying that insistence had none. They rot in ways nobody
notices until an agent acts on them:

    * a placeholder left as <...>, which the model fills in by inventing a value
    * a map stamped with a commit that is no longer HEAD
    * a FACTS.md whose commands all say FAILED, so there is no oracle at all
    * an AGENTS.md that is silently never read, because a higher-priority
      context file in the same repo shadows it

None of those announce themselves. Each produces an agent that is confidently
working from fiction.

This is the missing lint pass. Run it before every session, or wire it into a
pre-tool-call hook so a broken setup cannot start work.

    python bin/lint_agent_files.py <repo-root>
    python bin/lint_agent_files.py <repo-root> --strict   # warnings are failures

Exit 0 = usable. Exit 1 = at least one ERROR. Exit 2 = bad usage.

HERMES NOTE
-----------
Hermes discovers project context files first-match-wins in this order:

    .hermes.md / HERMES.md   (walks parents up to the git root)
    AGENTS.md / agents.md    (cwd only)
    CLAUDE.md / claude.md    (cwd only)
    .cursorrules

Only ONE is loaded per session. A repo containing both .hermes.md and AGENTS.md
loads only the former - your AGENTS.md is dead weight and nothing says so. This
linter reports that, because it is invisible at every other layer.

Context files are also capped at 20,000 characters, head+tail truncated beyond
that. A rule sitting in the middle of an oversized file silently disappears.

Standard library only. Python 3.9+.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

# Hermes truncates project context files beyond this, dropping the MIDDLE.
CONTEXT_FILE_CHAR_CAP = 20_000

# First match wins; earlier entries shadow later ones.
CONTEXT_PRIORITY = [
    ("(.hermes.md / HERMES.md)", ["\\.hermes\\.md", "HERMES\\.md"]),
    ("(AGENTS.md / agents.md)", ["AGENTS\\.md", "agents\\.md"]),
    ("(CLAUDE.md / claude.md)", ["CLAUDE\\.md", "claude\\.md"]),
    ("(.cursorrules)", ["\\.cursorrules"]),
]

# An unfilled placeholder is the highest-severity rot: the model invents a value
# rather than asking. Matches <...>, <one sentence>, <path>, etc.
PLACEHOLDER = re.compile(r"<[a-z][^<>\n]{0,60}>", re.I)

# Code legitimately contains angle brackets: `rg -t <lang>`, `git log -S "<term>"`,
# generics, shell usage strings. Those are documentation, not blanks to fill in.
# Strip BOTH fenced blocks and inline `code` spans first, or the linter cries wolf
# on its own template and gets ignored - a noisy linter is a disabled linter.
FENCE = re.compile(r"```.*?```", re.S)
INLINE_CODE = re.compile(r"`[^`\n]*`")


class Report:
    """Collects findings and decides the exit code."""

    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.notes: list[str] = []

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def note(self, msg: str) -> None:
        self.notes.append(msg)

    def render(self, strict: bool) -> int:
        for msg in self.errors:
            print(f"  ERROR    {msg}")
        for msg in self.warnings:
            print(f"  WARN     {msg}")
        for msg in self.notes:
            print(f"  ok       {msg}")
        print()
        if self.errors:
            print(f"RESULT: {len(self.errors)} error(s), {len(self.warnings)} warning(s)"
                  " - this repo is NOT ready for an agent session")
            return 1
        if self.warnings and strict:
            print(f"RESULT: {len(self.warnings)} warning(s), --strict - treating as failure")
            return 1
        if self.warnings:
            print(f"RESULT: usable, with {len(self.warnings)} warning(s)")
            return 0
        print("RESULT: all checks passed")
        return 0


def strip_fences(text: str) -> str:
    """Remove code so only prose is searched for unfilled placeholders.

    Fenced blocks are replaced with blank lines rather than deleted, so reported
    line numbers still match the file the user will open.
    """
    text = FENCE.sub(lambda m: "\n" * m.group(0).count("\n"), text)
    return INLINE_CODE.sub("", text)


def check_context_shadowing(root: Path, report: Report) -> None:
    """Detect a higher-priority context file silently shadowing AGENTS.md."""
    present: list[tuple[str, str]] = []
    for label, patterns in CONTEXT_PRIORITY:
        for pattern in patterns:
            name = pattern.replace("\\", "")
            if (root / name).is_file():
                present.append((label, name))
                break

    if not present:
        report.error("no agent context file found (expected AGENTS.md in the repo root) "
                     "- the agent will start with no project rules at all")
        return

    winner_label, winner_name = present[0]
    if len(present) > 1:
        shadowed = ", ".join(n for _, n in present[1:])
        # Deliberately does NOT say "delete them". An earlier wording said
        # "merge or delete the ones you do not want" and an agent read that as
        # authorisation - it deleted the user's CLAUDE.md and .cursorrules, which
        # belong to OTHER tools and were never this linter's business. Shadowing
        # is a fact to report; what to do about someone else's config file is a
        # human's call.
        report.error(
            f"'{winner_name}' SHADOWS {shadowed} - only the first is ever loaded, "
            f"so the others are never read by this agent.\n"
            f"             They may still be in use by other tools (Claude Code, "
            f"Cursor, Cline). Do NOT delete them on this basis. Consolidate the "
            f"rules you want into '{winner_name}' yourself.")
    else:
        report.note(f"context file: {winner_name} {winner_label}")


def check_file_size(path: Path, report: Report) -> None:
    """Warn before the host truncates the middle out of an oversized file."""
    try:
        size = len(path.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return
    if size > CONTEXT_FILE_CHAR_CAP:
        report.error(
            f"{path.name} is {size:,} chars, over the {CONTEXT_FILE_CHAR_CAP:,} cap - "
            "the MIDDLE will be dropped and those rules silently vanish. Split it.")
    elif size > CONTEXT_FILE_CHAR_CAP * 0.8:
        report.warn(f"{path.name} is {size:,} chars, close to the "
                    f"{CONTEXT_FILE_CHAR_CAP:,} truncation cap")


def check_placeholders(path: Path, report: Report) -> None:
    """An unfilled placeholder is worse than a missing file: it invites invention."""
    try:
        text = strip_fences(path.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return
    hits: list[str] = []
    for line_no, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith(">"):
            continue  # blockquote instructions to the human, not content
        for match in PLACEHOLDER.findall(line):
            # Table legends and type hints are not placeholders to fill.
            if match.lower() in ("<file>", "<line>", "<n>", "<hashes>", "<pkg>"):
                continue
            hits.append(f"{path.name}:{line_no}  {match}")
    if hits:
        report.error(f"{len(hits)} unfilled placeholder(s) - the model will invent "
                     f"values for these:")
        for hit in hits[:6]:
            report.error(f"    {hit}")
        if len(hits) > 6:
            report.error(f"    ...and {len(hits) - 6} more")
    else:
        report.note(f"{path.name} has no unfilled placeholders")


def git_head(root: Path) -> str:
    try:
        result = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=root,
                                capture_output=True, text=True, timeout=15)
        return result.stdout.strip() if result.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def check_map_freshness(root: Path, report: Report) -> None:
    """A stale map is worse than no map, because it is confidently wrong."""
    arch = root / ".agent" / "ARCHITECTURE.md"
    if not arch.is_file():
        report.warn("no .agent/ARCHITECTURE.md - run repo_graph.py "
                    "(the agent will have to explore, which is what this avoids)")
        return
    try:
        text = arch.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return

    match = re.search(r"at commit `([^`]+)`", text)
    if not match:
        report.warn("ARCHITECTURE.md has no commit stamp - cannot tell if it is stale")
        return
    stamped = match.group(1)
    head = git_head(root)
    if not head:
        report.note(f"ARCHITECTURE.md stamped {stamped} (not a git repo - "
                    "staleness cannot be checked)")
    elif stamped != head:
        report.error(f"ARCHITECTURE.md is STALE: stamped {stamped}, HEAD is {head}. "
                     "Regenerate with repo_graph.py before trusting it.")
    else:
        report.note(f"ARCHITECTURE.md is current ({stamped})")

    if "No runtime trace was merged" in text:
        report.warn("dynamic wiring in the map is INFERRED, not observed - "
                    "merge a runtime trace for ground truth (MANUAL step 4)")


def check_facts(root: Path, report: Report) -> None:
    """No VERIFIED command means no oracle, which means nothing is delegable.

    Reads facts.json rather than counting words in FACTS.md. Text counting was
    wrong twice over: it credited the INTERPRETER's VERIFIED stamp as though it
    were a command, and it counted the literal words 'FAILED'/'UNVERIFIED' out
    of the prose in the Rules section. The result claimed an oracle existed in a
    repo that had none - the precise failure this linter exists to catch.
    """
    facts_md = root / ".agent" / "FACTS.md"
    facts_json = root / ".agent" / "facts.json"
    if not facts_md.is_file() and not facts_json.is_file():
        report.warn("no .agent/FACTS.md - run repo_probe.py --deep "
                    "(paths and commands will be guesses)")
        return
    if not facts_json.is_file():
        report.warn("FACTS.md exists but facts.json does not - regenerate with "
                    "repo_probe.py so the oracle check can read structured data")
        return

    import json
    try:
        data = json.loads(facts_json.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        report.warn("facts.json is unreadable - regenerate with repo_probe.py")
        return

    # --- tamper check -----------------------------------------------------
    # A model that cannot satisfy the oracle will try to satisfy the CHECK.
    # Observed: an agent grepped this linter's source, found it reads facts.json,
    # hand-wrote a facts.json with a fabricated VERIFIED command, and re-ran the
    # linter to get a pass. The repo had no working command at all.
    stamp = data.get("integrity")
    if not stamp:
        report.warn("facts.json has no integrity stamp - generated by an old "
                    "repo_probe.py, or written by hand. Regenerate it.")
    else:
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
        expected = hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]
        if expected != stamp:
            report.error(
                "facts.json HAS BEEN MODIFIED BY HAND - its integrity stamp does "
                "not match its contents. Commands listed here are NOT evidence. "
                "Regenerate with repo_probe.py --deep and do not trust any result "
                "produced while this file was in its edited state.")
        else:
            report.note("facts.json integrity stamp verifies")

    commands = data.get("commands") or []
    verified = [c for c in commands if c.get("status") == "VERIFIED"]
    failed = [c for c in commands if c.get("status") == "FAILED"]
    unverified = [c for c in commands if c.get("status") == "UNVERIFIED"]

    if not verified:
        report.error(
            f"FACTS.md lists NO verified command ({len(commands)} detected, "
            f"{len(failed)} failed, {len(unverified)} unverified) - there is no "
            "oracle here, so no task in this repo is safely delegable")
    else:
        roles = ", ".join(sorted({c["role"] for c in verified}))
        report.note(f"{len(verified)} verified command(s) available as oracles: {roles}")

    if failed:
        names = ", ".join(sorted({c["role"] for c in failed}))
        report.warn(f"{len(failed)} FAILED command(s) [{names}] - configured but not "
                    "installed; install them to gain an oracle")
    if unverified:
        report.warn(f"{len(unverified)} UNVERIFIED row(s) - re-run repo_probe.py --deep")

    interpreters = data.get("interpreters") or []
    if not interpreters:
        report.warn("no project interpreter found - the agent may fall back to the "
                    "system Python and install into the wrong environment")
    elif interpreters[0].get("status") != "VERIFIED":
        report.error(f"project interpreter `{interpreters[0].get('path')}` did not "
                     "answer --version - every command built on it will fail")


# An oracle built only from these cannot fail once any edit is made. Observed:
# `git diff --name-only | grep -q README.md` set as the closure for "edit
# README.md" - it asks "did the file I just edited get edited?"
TAUTOLOGY_MARKERS = ("git diff", "git status", "ls ", "test -f", "cat ", "head ",
                     "wc -", "stat ", "find ")
# A real oracle runs one of these: something that can be RED.
ORACLE_MARKERS = ("pytest", "unittest", "mypy", "flake8", "ruff", "black", "pyright",
                  "tsc", "eslint", "jest", "vitest", "npm test", "npm run",
                  "cargo test", "go test", "make", "node --check", "python -m",
                  "verify-absence")


def check_agent_state(root: Path, report: Report) -> None:
    """Warn when a task is mid-flight, or when its closure proves nothing."""
    agent_dir = root / ".agent"
    worklist = agent_dir / "worklist.txt"
    closure = agent_dir / "closure.txt"
    if not worklist.is_file():
        return
    try:
        pending = [ln for ln in worklist.read_text(encoding="utf-8",
                                                   errors="replace").splitlines()
                   if ln.strip()]
    except OSError:
        return
    if not pending:
        return

    text = ""
    if closure.is_file():
        text = closure.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        report.error(f"worklist has {len(pending)} pending unit(s) but NO closure "
                     "oracle is set - the agent cannot prove it is finished. "
                     "Set one: agent-state.sh closure \"<command>\"")
        return

    lowered = text.lower()

    # An unknown flag swallowed into the command string means the oracle is
    # malformed and will not run as intended. Seen when an agent invented a
    # --repo flag the scripts do not have; it landed inside the grep arguments.
    if "--repo" in lowered or lowered.endswith("/"):
        report.error("closure command contains a stray argument (e.g. `--repo`) - "
                     f"it is malformed and will not test what you think:\n"
                     f"             {text}")

    has_real = any(m in lowered for m in ORACLE_MARKERS)
    only_inspection = (any(m in lowered for m in TAUTOLOGY_MARKERS) and not has_real)
    if only_inspection:
        report.error(
            "closure oracle is a TAUTOLOGY - it only inspects state, so it cannot "
            "fail once an edit is made:\n"
            f"             {text}\n"
            "             An oracle must be able to go RED. Use a test, build, "
            "typecheck, or lint command from FACTS.md.")
    elif not has_real:
        report.warn(f"closure oracle does not obviously run a check tool - confirm "
                    f"it can actually fail:\n             {text}")
    else:
        report.note(f"closure oracle set, {len(pending)} unit(s) pending")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Lint the agent instruction files for a repo.")
    parser.add_argument("root", nargs="?", default=".", help="repository root")
    parser.add_argument("--strict", action="store_true",
                        help="treat warnings as failures (use in hooks/CI)")
    args = parser.parse_args()

    root = Path(args.root.strip()).expanduser()
    if not root.is_dir():
        print(f"error: not a directory: [{root}]", file=sys.stderr)
        return 2
    root = root.resolve()

    print(f"linting: {root}\n")
    report = Report()

    check_context_shadowing(root, report)
    for name in ("AGENTS.md", "agents.md", ".hermes.md", "HERMES.md"):
        candidate = root / name
        if candidate.is_file():
            check_file_size(candidate, report)
            check_placeholders(candidate, report)
            break
    check_map_freshness(root, report)
    check_facts(root, report)
    check_agent_state(root, report)

    return report.render(args.strict)


if __name__ == "__main__":
    sys.exit(main())
