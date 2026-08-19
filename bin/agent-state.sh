#!/usr/bin/env bash
# agent-state.sh — external state for the agent. Replaces in-context STATE blocks.
#
# Give the agent this script and forbid it from tracking progress in its replies.
#
#   ./agent-state.sh init  <goal>       start a task
#   ./agent-state.sh add   <unit> ...   queue units (files, symbols, whatever)
#   ./agent-state.sh addf  <file>       queue every line of a file as a unit
#   ./agent-state.sh next               print the next pending unit (empty = done)
#   ./agent-state.sh done  <unit>       mark complete
#   ./agent-state.sh skip  <unit> <why> mark skipped with a reason
#   ./agent-state.sh ask   <unit> <q>   escalate to the human, continue working
#   ./agent-state.sh status             counts + goal + closure condition
#   ./agent-state.sh closure <cmd>      set the oracle command that proves completion
#   ./agent-state.sh check              run the oracle; exit 0 only if it passes

set -uo pipefail

# --repo <path> targets a repository other than the current directory.
#
# This exists because an agent INVENTED it. Given a task in another repo, a model
# appended '--repo D:/path/' to every call; the flag was unknown, so it was
# swallowed as literal text into the goal string and into the closure command:
#
#   closure.txt: git diff --name-only | grep -q README.md --repo D:/path/
#
# The oracle was silently malformed. Two lessons, both applied below: support the
# flag people reach for, and REJECT unknown flags loudly instead of absorbing
# them into data.
REPO=""
ARGS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --repo)
      REPO="${2:-}"
      [ -n "$REPO" ] || { echo "--repo needs a path" >&2; exit 2; }
      shift 2 ;;
    --repo=*) REPO="${1#--repo=}"; shift ;;
    --) shift; while [ $# -gt 0 ]; do ARGS+=("$1"); shift; done ;;
    --*)
      echo "unknown option: $1" >&2
      echo "known options: --repo <path>" >&2
      echo "(refusing to treat it as text - that silently corrupts goals and oracles)" >&2
      exit 2 ;;
    *) ARGS+=("$1"); shift ;;
  esac
done
set -- ${ARGS+"${ARGS[@]}"}

if [ -n "$REPO" ]; then
  REPO="${REPO#"${REPO%%[![:space:]]*}"}"; REPO="${REPO%"${REPO##*[![:space:]]}"}"
  cd "$REPO" || { echo "no such directory: [$REPO]" >&2; exit 2; }
fi

D=".agent"; mkdir -p "$D"
W="$D/worklist.txt"; DONE="$D/done.txt"; SKIP="$D/skipped.txt"
Q="$D/questions.md"; GOAL="$D/goal.txt"; ORACLE="$D/closure.txt"
touch "$W" "$DONE" "$SKIP" "$Q"

pending() { grep -vxF -f <(cat "$DONE" "$SKIP" 2>/dev/null; echo) "$W" 2>/dev/null | sed '/^$/d'; }

case "${1:-status}" in
  init)
    shift; : > "$W"; : > "$DONE"; : > "$SKIP"; : > "$Q"
    echo "${*:-unnamed task}" > "$GOAL"
    echo "# Questions — human answers go in decisions.md" > "$Q"
    echo "initialised: $(cat "$GOAL")"
    ;;
  add)
    shift; for u in "$@"; do grep -qxF "$u" "$W" || echo "$u" >> "$W"; done
    echo "queued $#; pending: $(pending | wc -l | tr -d ' ')"
    ;;
  addf)
    f="${2:?usage: addf <file>}"
    n=0; while IFS= read -r u; do
      u="$(echo "$u" | tr -d '\r' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
      [ -z "$u" ] && continue
      grep -qxF "$u" "$W" || { echo "$u" >> "$W"; n=$((n+1)); }
    done < "$f"
    echo "queued $n; pending: $(pending | wc -l | tr -d ' ')"
    ;;
  next)   pending | head -1 ;;
  done)   echo "${2:?usage: done <unit>}" >> "$DONE"; echo "done: $2 | pending: $(pending | wc -l | tr -d ' ')" ;;
  skip)   u="${2:?}"; shift 2; echo "$u" >> "$SKIP"; echo "$u :: ${*:-no reason}" >> "$D/skip-reasons.txt"
          echo "skipped: $u | pending: $(pending | wc -l | tr -d ' ')" ;;
  ask)
    u="${2:?}"; shift 2
    { echo; echo "## $u"; echo "Q: ${*:-unspecified}"; echo "A: "; } >> "$Q"
    echo "escalated: $u — continue with other units, do not block"
    ;;
  closure) shift; echo "$*" > "$ORACLE"; echo "closure oracle set: $*" ;;
  check)
    [ -s "$ORACLE" ] || { echo "NO ORACLE SET — this task is not agent-ready. Use: closure <cmd>" >&2; exit 2; }
    p=$(pending | wc -l | tr -d ' ')
    [ "$p" -gt 0 ] && { echo "NOT DONE — $p unit(s) pending"; exit 1; }
    echo "running oracle: $(cat "$ORACLE")"
    if bash -c "$(cat "$ORACLE")"; then echo "CLOSED — oracle passed"; exit 0
    else echo "OPEN — oracle failed"; exit 1; fi
    ;;
  status)
    echo "goal:     $(cat "$GOAL" 2>/dev/null || echo '(none)')"
    echo "oracle:   $(cat "$ORACLE" 2>/dev/null || echo '(NONE SET — task is not agent-ready)')"
    echo "queued:   $(sed '/^$/d' "$W" | wc -l | tr -d ' ')"
    echo "done:     $(sed '/^$/d' "$DONE" | wc -l | tr -d ' ')"
    echo "skipped:  $(sed '/^$/d' "$SKIP" | wc -l | tr -d ' ')"
    echo "pending:  $(pending | wc -l | tr -d ' ')"
    echo "questions:$(grep -c "^## " "$Q" 2>/dev/null || true)"
    ;;
  *) sed -n '2,20p' "$0" ;;
esac
