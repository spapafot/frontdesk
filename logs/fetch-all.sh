#!/usr/bin/env bash
# Dump recent logs for everything into one timestamped folder under logs/out/.
#
# For each Lambda it writes both a full log and an errors-only log. For the
# Cloudflare Worker (+ Durable Objects) it optionally captures a live tail
# window - `wrangler tail` is live-only, so pass --worker-seconds and generate
# some traffic while it runs, or skip it and use the dashboard for history.
#
# Usage:
#   ./fetch-all.sh [--since <dur>] [--worker-seconds <n>]
#
# Options:
#   --since <dur>          Lambda look-back window (default 3h).
#   --worker-seconds <n>   Also capture the worker tail for n seconds.
#   -h, --help
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=config.sh
source "$HERE/config.sh"

SINCE="3h"
WSECS=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --since)          SINCE="$2"; shift 2 ;;
    --worker-seconds) WSECS="$2"; shift 2 ;;
    -h|--help) awk 'NR==1{next} /^#/{sub(/^# ?/,"");print;next}{exit}' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

# Pin one shared run folder for every child script.
export RUN_TS="$(date +%Y%m%d-%H%M%S)"
RD="$OUT_DIR/$RUN_TS"
mkdir -p "$RD"
echo "==> writing to $RD" >&2

# Lambdas: full + errors-only for both functions.
"$HERE/fetch-lambda.sh" all --since "$SINCE" --save
"$HERE/fetch-lambda.sh" all --since "$SINCE" --errors --save

# Worker (+ Durable Objects): optional live capture window.
if [[ -n "$WSECS" ]]; then
  "$HERE/fetch-worker.sh" --seconds "$WSECS" --json --save || true
else
  echo "==> skipped worker tail (pass --worker-seconds N to capture; it is live-only)" >&2
fi

{
  echo "run:        $RUN_TS"
  echo "region:     $AWS_REGION"
  echo "since:      $SINCE"
  echo "lambdas:    $BACKEND_LAMBDA, $INGESTION_LAMBDA"
  echo "worker:     $CF_WORKER (DOs: $CF_DO_CLASSES)"
  echo "worker cap: ${WSECS:-skipped}"
  echo
  echo "files:"
  ls -1 "$RD"
} > "$RD/summary.txt"

echo "==> done. summary:" >&2
cat "$RD/summary.txt"
