#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# Keep deployments production-bound even when this script runs from a feature
# branch. Without --branch, Wrangler automatically creates a preview upload.
PAGES_PRODUCTION_BRANCH="${PAGES_PRODUCTION_BRANCH:-dev}"

cd "$REPO_ROOT/site"
npm run build
npx wrangler pages deploy dist \
  --project-name=plugandplay-site \
  --branch="$PAGES_PRODUCTION_BRANCH"
