#!/usr/bin/env bash
# repo-orient.sh — Phase 0. Generates a REPO-MAP.md skeleton for an unfamiliar repo.
# Usage:  ./repo-orient.sh [repo-root]
# Output: .agent/REPO-MAP.md   (fill in the JUDGEMENT sections by hand, then commit)

set -uo pipefail

ROOT="${1:-.}"
# Strip surrounding whitespace. A stray leading space from a copy-paste
# (./repo-orient.sh " D:\repo") is invisible in the shell and in the error
# message, so it reads as "the script is broken" rather than "bad argument".
ROOT="${ROOT#"${ROOT%%[![:space:]]*}"}"
ROOT="${ROOT%"${ROOT##*[![:space:]]}"}"
[ -n "$ROOT" ] || ROOT="."
# Backslash paths (D:\repo) work in Git Bash; forward slashes work everywhere.
cd "$ROOT" || { echo "no such directory: [$ROOT]" >&2; exit 1; }
mkdir -p .agent
OUT=".agent/REPO-MAP.md"
echo "scanning: $(pwd)"

# Anchored to whole path segments. An unanchored regex would drop 'routes.ts'
# (contains 'out'), 'layout.tsx', 'builder.ts', 'distance.ts' — a silent, nasty bug.
# venv[^/]* catches venv, venv_311, venv311; site-packages catches the payload of
# any virtualenv whatever its top directory is named. Without these, a Python repo
# reports its interpreter's stdlib as its largest source root.
EXCLUDE='(^|/)(node_modules|\.git|\.agent|\.idea|dist|build|out|coverage|\.next|target|vendor|__pycache__|\.venv[^/]*|venv[^/]*|site-packages|\.tox|\.mypy_cache|\.pytest_cache|\.ruff_cache|\.eggs|htmlcov)(/|$)'

{
  echo "# REPO-MAP"
  echo
  echo "_Generated $(date -u '+%Y-%m-%d %H:%M UTC') by repo-orient.sh. Sections marked JUDGEMENT need a human._"
  echo
  echo "## JUDGEMENT: what this project is"
  echo
  echo "<one paragraph — what it does, who uses it, what the main flow is>"
  echo

  echo "## Manifests"
  echo '```'
  find . -maxdepth 3 \
    \( -name 'package.json' -o -name 'pyproject.toml' -o -name 'Cargo.toml' \
       -o -name 'go.mod' -o -name '*.csproj' -o -name 'pom.xml' -o -name 'requirements*.txt' \) \
    2>/dev/null | grep -Ev "$EXCLUDE" | sort
  echo '```'
  echo

  if [ -f package.json ]; then
    echo "### package.json scripts"
    echo '```'
    if command -v node >/dev/null 2>&1; then
      node -e 'const p=require("./package.json");for(const[k,v]of Object.entries(p.scripts||{}))console.log(k.padEnd(18)+v)' 2>/dev/null
    else
      sed -n '/"scripts"/,/}/p' package.json
    fi
    echo '```'
    echo
    echo "### workspaces / monorepo"
    echo '```'
    if command -v node >/dev/null 2>&1; then
      node -e 'const p=require("./package.json");const w=p.workspaces;console.log(w?JSON.stringify(w):"(no workspaces field)")' 2>/dev/null
    else
      grep -o '"workspaces"[^]]*]' package.json 2>/dev/null || echo "(no workspaces field)"
    fi
    ls -d packages/*/ apps/*/ services/*/ 2>/dev/null || true
    echo '```'
    echo
  fi

  echo "## Source roots by size"
  echo
  echo "| Directory | Files | Lines |"
  echo "|---|---:|---:|"
  find . -maxdepth 2 -type d 2>/dev/null | grep -Ev "$EXCLUDE" | grep -v '^\.$' | sort | while read -r d; do
    # One walk per directory, reused for both columns. The previous version
    # walked each subtree twice, which is what made this the slow section.
    list=$(find "$d" -type f \
      \( -name '*.ts' -o -name '*.tsx' -o -name '*.js' -o -name '*.jsx' \
         -o -name '*.py' -o -name '*.rs' -o -name '*.go' -o -name '*.cs' -o -name '*.java' \) \
      2>/dev/null | grep -Ev "$EXCLUDE")
    files=$(printf '%s\n' "$list" | grep -c . )
    [ "$files" -eq 0 ] 2>/dev/null && continue
    lines=$(printf '%s\n' "$list" | tr '\n' '\0' | xargs -0 cat 2>/dev/null | wc -l | tr -d ' ')
    echo "| \`$d\` | $files | $lines |"
  done
  echo

  echo "## JUDGEMENT: directory responsibilities"
  echo
  echo "| Path | Responsibility |"
  echo "|---|---|"
  echo "| \`<path>\` | \`<what lives here>\` |"
  echo

  echo "## Entry point candidates"
  echo '```'
  # by conventional name
  find . -maxdepth 4 -type f \
    \( -name 'main.*' -o -name 'index.ts' -o -name 'index.tsx' -o -name 'index.js' \
       -o -name 'index.mjs' -o -name 'index.cjs' \
       -o -name 'app.ts' -o -name 'App.tsx' -o -name 'app.py' -o -name '__main__.py' \
       -o -name 'cli.py' -o -name 'manage.py' -o -name 'run.py' -o -name 'server.*' \) \
    2>/dev/null | grep -Ev "$EXCLUDE" | sort | head -25
  # Convention-only matching finds nothing in repos whose entry point is named
  # after the project (facefusion.py, run.js). Root-level scripts are always
  # worth listing — they are where such entry points actually live.
  echo "-- root-level scripts --"
  find . -maxdepth 1 -type f \
    \( -name '*.py' -o -name '*.js' -o -name '*.mjs' -o -name '*.sh' -o -name '*.bat' \) \
    2>/dev/null | grep -Ev "$EXCLUDE" | sort | head -20
  if [ -f package.json ] && command -v node >/dev/null 2>&1; then
    echo "-- package.json main/bin --"
    node -e 'const p=require("./package.json");if(p.main)console.log("main: "+p.main);if(p.bin)console.log("bin:  "+JSON.stringify(p.bin))' 2>/dev/null
  fi
  echo '```'
  echo

  echo "## Config, env, and flags"
  echo '```'
  find . -maxdepth 3 -type f \
    \( -name '*.config.*' -o -name '.env*' -o -name 'tsconfig*.json' \
       -o -name '*.toml' -o -name '*.yaml' -o -name '*.yml' \
       -o -name '*.ini' -o -name '*.cfg' -o -name 'Makefile' \
       -o -name 'Dockerfile*' -o -name 'docker-compose*' \) \
    2>/dev/null | grep -Ev "$EXCLUDE" | sort | head -40
  echo '```'
  echo

  echo "## Largest source files — read these with line ranges, never whole"
  echo '```'
  find . -type f \
    \( -name '*.ts' -o -name '*.tsx' -o -name '*.js' -o -name '*.py' -o -name '*.rs' -o -name '*.go' \) \
    2>/dev/null | grep -Ev "$EXCLUDE" | tr '\n' '\0' | xargs -0 wc -l 2>/dev/null \
    | grep -Ev '^[[:space:]]*[0-9]+[[:space:]]+total$' | sort -rn | head -15
  echo '```'
  echo

  echo "## License"
  echo '```'
  lic=$(ls LICENSE LICENSE.md LICENSE.txt COPYING 2>/dev/null | head -1)
  if [ -n "$lic" ]; then head -5 "$lic"; else echo "(no LICENSE file — resolve before distributing changes)"; fi
  echo '```'
  echo

  echo "## Repo history"
  echo '```'
  if [ -d .git ]; then
    echo "commits:      $(git rev-list --count HEAD 2>/dev/null)"
    echo "first commit: $(git log --reverse --format=%ad --date=short 2>/dev/null | head -1)"
    echo "last commit:  $(git log -1 --format=%ad --date=short 2>/dev/null)"
    echo "branch:       $(git rev-parse --abbrev-ref HEAD 2>/dev/null)"
  else
    echo "(not a git repo — history-layer techniques unavailable)"
  fi
  echo '```'
  echo

  echo "## JUDGEMENT: landmines"
  echo
  echo "- <files never to read whole>"
  echo "- <generated directories never to edit>"
  echo "- <behaviour enforced server-side that client changes cannot affect>"
} > "$OUT"

echo "wrote $OUT"
echo "Now fill the three JUDGEMENT sections by hand, then: git add $OUT && git commit"
