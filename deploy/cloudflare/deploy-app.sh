#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# These Direct Upload projects use `dev` as their Cloudflare production branch.
# Always pass it explicitly: otherwise Wrangler detects the checked-out Git
# branch and turns feature-branch uploads into preview deployments.
PAGES_PRODUCTION_BRANCH="${PAGES_PRODUCTION_BRANCH:-dev}"

cd "$REPO_ROOT/frontend"
npm run build
npx wrangler pages deploy dist \
  --project-name=plugandplay-admin \
  --branch="$PAGES_PRODUCTION_BRANCH"
