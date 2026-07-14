#!/usr/bin/env bash
# Shared config for the log-fetch scripts. Source it from the others:
#   source "$(dirname "${BASH_SOURCE[0]}")/config.sh"
# Override any value by exporting it first, e.g.:
#   AWS_REGION=eu-west-1 ./fetch-lambda.sh backend
set -euo pipefail

# Git Bash / MSYS rewrites leading-slash args (e.g. "/aws/lambda/...") into
# Windows paths, which breaks CloudWatch log-group names. Disable that. Harmless
# on Linux/macOS where the variable is simply ignored.
export MSYS_NO_PATHCONV=1

# --- AWS ------------------------------------------------------------------
export AWS_REGION="${AWS_REGION:-eu-central-1}"
# Lambda function names. Their CloudWatch log group is /aws/lambda/<name>.
export BACKEND_LAMBDA="${BACKEND_LAMBDA:-plugandplay-support}"
export INGESTION_LAMBDA="${INGESTION_LAMBDA:-plugandplay-doc-ingestion}"

# --- Cloudflare -----------------------------------------------------------
export CF_WORKER="${CF_WORKER:-plugandplay-api}"
# Pin the Cloudflare account so `wrangler tail` doesn't prompt when logged into
# more than one. (Use the current var name, not the deprecated CF_ACCOUNT_ID.)
export CLOUDFLARE_ACCOUNT_ID="${CLOUDFLARE_ACCOUNT_ID:-6259fbaea472fcb4afffc8e073a931f8}"
# Durable Object classes defined in the worker. DOs run *inside* the worker,
# so their logs and exceptions surface in the worker's own tail stream - there
# is no separate DO log source to fetch.
export CF_DO_CLASSES="${CF_DO_CLASSES:-BusinessInbox ConversationRoom}"

# --- Paths / output -------------------------------------------------------
LOGS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export LOGS_DIR
export WORKER_DIR="${WORKER_DIR:-$LOGS_DIR/../deploy/cloudflare/worker}"
export OUT_DIR="${OUT_DIR:-$LOGS_DIR/out}"

# CloudWatch metric-filter pattern matching common error tokens (an OR of
# terms; the leading `?` makes each term optional).
: "${ERROR_PATTERN:=?ERROR ?Error ?Exception ?Traceback ?CRITICAL ?\"Task timed out\"}"
export ERROR_PATTERN

# --- Helpers --------------------------------------------------------------
# need <cmd> [hint]  - abort with a clear message if a required tool is missing.
need() {
  command -v "$1" >/dev/null 2>&1 && return 0
  echo "error: '$1' not found on PATH. ${2:-}" >&2
  exit 127
}

# Resolve a wrangler runner: prefer a global install, else the worker's local
# copy via npx (no network fetch). Populates the WRANGLER array.
resolve_wrangler() {
  if command -v wrangler >/dev/null 2>&1; then
    WRANGLER=(wrangler)
  elif command -v npx >/dev/null 2>&1; then
    WRANGLER=(npx --no-install wrangler)
  else
    echo "error: neither 'wrangler' nor 'npx' found on PATH." >&2
    echo "       install wrangler, or run from a machine with the worker deps." >&2
    exit 127
  fi
}

# Timestamped run directory shared across scripts in one fetch-all invocation.
run_dir() {
  local ts="${RUN_TS:-$(date +%Y%m%d-%H%M%S)}"
  echo "$OUT_DIR/$ts"
}
