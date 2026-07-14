#!/usr/bin/env bash
# Capture logs for the Cloudflare Worker (plugandplay-api) and its Durable
# Objects (BusinessInbox, ConversationRoom) via `wrangler tail`.
#
# Durable Objects run *inside* the worker, so their console output and thrown
# exceptions appear in the same tail stream - there is no separate DO log
# source. `wrangler tail` is LIVE-ONLY: it streams events as they occur, it does
# not fetch past logs. Start it, then exercise the widget / live chat so events
# flow. For historical worker logs use the dashboard (Workers > plugandplay-api
# > Logs - observability is enabled) or set up Logpush.
#
# Usage:
#   ./fetch-worker.sh [options]
#
# Options:
#   --errors        Only failed invocations (wrangler --status error).
#   --do            Only lines mentioning a Durable Object class
#                   ($CF_DO_CLASSES). Best-effort: matches when your DO code
#                   logs the class/room context.
#   --seconds <n>   Auto-stop after n seconds (needs `timeout`); else Ctrl-C.
#   --json          Emit JSON lines instead of the pretty view.
#   --save          Write the capture to logs/out/<timestamp>/worker[.jsonl|.log]
#   -h, --help      Show this help.
#
# Needs wrangler (global, or the worker's local copy via npx) and `wrangler login`.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=config.sh
source "$HERE/config.sh"

ERRORS=0
DO_ONLY=0
JSON=0
SAVE=0
SECS=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --errors)  ERRORS=1; shift ;;
    --do)      DO_ONLY=1; shift ;;
    --json)    JSON=1; shift ;;
    --save)    SAVE=1; shift ;;
    --seconds) SECS="$2"; shift 2 ;;
    -h|--help) awk 'NR==1{next} /^#/{sub(/^# ?/,"");print;next}{exit}' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

resolve_wrangler

flags=(tail "$CF_WORKER")
[[ $ERRORS -eq 1 ]] && flags+=(--status error)
if [[ $JSON -eq 1 ]]; then flags+=(--format json); else flags+=(--format pretty); fi

# Optional auto-stop wrapper.
runner=()
if [[ -n "$SECS" ]]; then
  if command -v timeout >/dev/null 2>&1; then
    runner=(timeout "${SECS}s")
  else
    echo "warn: 'timeout' not found - ignoring --seconds; press Ctrl-C to stop." >&2
  fi
fi

# DO grep regex: BusinessInbox|ConversationRoom
do_re="$(echo "$CF_DO_CLASSES" | tr ' ' '|')"

out=""
if [[ $SAVE -eq 1 ]]; then
  RD="$(run_dir)"; mkdir -p "$RD"
  if [[ $JSON -eq 1 ]]; then out="$RD/worker.jsonl"; else out="$RD/worker.log"; fi
fi

e=""; [[ $ERRORS -eq 1 ]] && e=" (errors only)"
d=""; [[ $DO_ONLY -eq 1 ]] && d=" (DO lines only)"
s=""; [[ -n "$SECS" ]] && s=", ${SECS}s"
echo "==> tailing worker '$CF_WORKER'$e$d$s" >&2
echo "    (live stream - trigger widget/live-chat traffic to see events)" >&2

cd "$WORKER_DIR"

# The capture may exit non-zero (timeout=124, or grep finds nothing) - that is
# normal here, so don't let errexit/pipefail abort on it.
set +e
if   [[ $DO_ONLY -eq 1 && $SAVE -eq 1 ]]; then
  "${runner[@]}" "${WRANGLER[@]}" "${flags[@]}" | grep --line-buffered -E "$do_re" | tee "$out"
elif [[ $DO_ONLY -eq 1 ]]; then
  "${runner[@]}" "${WRANGLER[@]}" "${flags[@]}" | grep --line-buffered -E "$do_re"
elif [[ $SAVE -eq 1 ]]; then
  "${runner[@]}" "${WRANGLER[@]}" "${flags[@]}" | tee "$out"
else
  "${runner[@]}" "${WRANGLER[@]}" "${flags[@]}"
fi
rc=$?
set -e

[[ -n "$out" ]] && echo "    saved -> $out" >&2
# 124 = clean timeout stop; treat as success.
[[ $rc -eq 124 ]] && rc=0
exit $rc
