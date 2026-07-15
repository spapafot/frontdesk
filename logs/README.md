# logs/ - fetch runtime logs

Bash helpers to pull logs from the two AWS Lambdas and the Cloudflare Worker
(plus its Durable Objects). Run them from Git Bash on Windows or any POSIX shell.

| Script            | Source                    | Fetches                                            |
| ----------------- | ------------------------- | -------------------------------------------------- |
| `fetch-lambda.sh` | CloudWatch Logs (AWS CLI) | `plugandplay-support`, `plugandplay-doc-ingestion` |
| `fetch-worker.sh` | `wrangler tail` (live)    | Worker `plugandplay-api` + Durable Objects         |
| `fetch-all.sh`    | both of the above         | Everything into one timestamped folder             |
| `config.sh`       | -                         | Shared names/region/paths (sourced by the rest)    |

Captured output lands in `logs/out/<timestamp>/` (git-ignored).

## Prerequisites

- **AWS**: AWS CLI **v2** authenticated for the account (`aws sts get-caller-identity`
  works). Region defaults to `eu-central-1`.
- **Cloudflare**: `wrangler` - a global install, or the worker's local copy
  (auto-used via `npx` when run near `deploy/cloudflare/worker/`). Log in once
  with `wrangler login`.

## Lambda logs

```bash
cd logs
./fetch-lambda.sh                       # both lambdas, last 1h
./fetch-lambda.sh backend --since 30m   # backend only, last 30 min
./fetch-lambda.sh ingestion --errors    # ingestion, error lines only
./fetch-lambda.sh backend --follow      # live stream (Ctrl-C to stop)
./fetch-lambda.sh all --since 6h --save # write to logs/out/<ts>/
```

`--since` accepts `30m`, `2h`, `1d`, or an absolute time like
`2026-07-14T09:00:00`. `--errors` uses a metric-filter pattern (`ERROR`,
`Exception`, `Traceback`, `Task timed out`, …); override it with
`ERROR_PATTERN=...`.

## Worker + Durable Object logs

Durable Objects (`BusinessInbox`, `ConversationRoom`) run **inside** the worker,
so their logs and exceptions show up in the worker's own stream - there is no
separate DO log to fetch.

```bash
cd logs
./fetch-worker.sh                    # live pretty stream (Ctrl-C to stop)
./fetch-worker.sh --errors           # failed invocations only
./fetch-worker.sh --do               # only lines mentioning a DO class
./fetch-worker.sh --seconds 60 --save --json   # capture 60s to logs/out/<ts>/
```

> `wrangler tail` is **live-only** - it streams events as they happen and does
> not return past logs. Start it, then drive traffic (open the widget, start a
> live chat). For **historical** worker/DO logs use the Cloudflare dashboard
> (Workers → `plugandplay-api` → Logs; observability is enabled at 100%
> sampling) or configure Logpush.

## Everything at once

```bash
cd logs
./fetch-all.sh                              # both lambdas (3h) → logs/out/<ts>/
./fetch-all.sh --since 12h --worker-seconds 90
```

Writes `plugandplay-support.log`, `plugandplay-support.errors.log`, the same
pair for ingestion, an optional `worker.jsonl`, and a `summary.txt`.

## Overrides

Every value in `config.sh` is env-overridable, e.g.:

```bash
AWS_REGION=eu-west-1 ./fetch-lambda.sh backend
CF_WORKER=some-other-worker ./fetch-worker.sh
```
