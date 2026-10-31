#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# Keep deployments production-bound even when this script runs from a feature
# branch. Without --branch, Wrangler automatically creates a preview upload.
PAGES_PRODUCTION_BRANCH="${PAGES_PRODUCTION_BRANCH:-dev}"

cd "$REPO_ROOT/frontend"
npm run build:widget
npx wrangler pages deploy dist-widget \
  --project-name=plugandplay-widget \
  --branch="$PAGES_PRODUCTION_BRANCH"
