# Deploying Artemis on Specific

This is the play-by-play for taking the repo from a fresh clone to a live URL
on Specific's hosted infra. It assumes you've already merged the four-PR
stack (#5 web port, #6 auth, #7 backend split + storage + jobs).

## Architecture summary

```
                ┌──────────────────────┐
 browser ──HTTPS┤  service "web"        │ next 16, base = node
                │  apps/web/            │ pg pool → postgres.main
                │  npx next start       │
                └──────────┬───────────┘
                           │ http (ARTEMIS_API_URL, X-Artemis-Service-Key)
                           ▼
                ┌──────────────────────┐
                │  service "api"        │ python 3.12, base = python
                │  apps/api/            │ pg pool → postgres.main
                │  python -m apps.api   │ orchestrate pipeline
                │                       │ writes to storage.media (S3)
                └──────────┬───────────┘
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
       postgres.main             storage.media
       (managed)                 (S3-compatible)
```

The two services share the same Postgres and the same object-storage bucket.
The web container is Node-only; all Python lives in the api container.

Resources declared in `specific.hcl`:

| Resource         | Kind     | What it does                                  |
| ---------------- | -------- | --------------------------------------------- |
| `build "web"`    | node     | Next.js production build out of `apps/web/`.  |
| `build "api"`    | python   | `python -m apps.api` boots uvicorn.           |
| `service "web"`  | public   | Browser entry point.                          |
| `service "api"`  | public   | Internal callers go through `service.api.url`. |
| `postgres "main"`| managed  | Schema is bootstrapped at api startup.        |
| `storage "media"`| S3-like  | Highlight + overlay videos live here.         |

## Prereqs

- Specific CLI installed and authenticated:
  ```bash
  specific --version            # any recent version
  specific project list         # confirms you can see your org
  ```
- Node 20+ for local builds (only matters if you want to test the web image).
- Python 3.12 venv at the repo root (for local api dev).

## First-time deploy walkthrough

### 1. Validate the config

```bash
specific check
```

Expected output:
```
Configuration is valid
Builds (2):  - api (python), - web (node)
Services (2): - api, - web
Postgres (1): - main
Storage (1):  - media
```

If `specific check` complains about anything, do not move on — `specific
deploy` will silently inherit the same problems.

### 2. Create a project (only on the first deploy)

```bash
specific project new artemis
```

This writes the project id to `.projectid` (gitignored) so subsequent
`specific deploy` invocations know where they go.

### 3. Set the secret(s)

Only one secret is required by the app code: a shared service key between
`web` and `api`. The HCL leaves it empty so local dev works without one;
production must set it.

```bash
specific deploy --secret ARTEMIS_API_KEY=$(openssl rand -hex 32)
```

Postgres URL and S3 credentials are auto-provisioned by Specific from the
`postgres "main"` and `storage "media"` blocks — you do not set them by
hand.

> The api treats an empty `ARTEMIS_API_KEY` as "open mode" for local dev. In
> production this would let anyone POST to `/process-upload` directly.
> Always set it.

### 4. Deploy

```bash
specific deploy
```

On a clean deploy this:
1. Builds the `web` image (Node) and the `api` image (Python).
2. Provisions Postgres and the S3 bucket.
3. Starts the api service first; its FastAPI lifespan hook runs
   `strava_climbing.db.init_db()` (with retries) before serving traffic.
4. Starts the web service, which gets `ARTEMIS_API_URL = service.api.url`
   injected automatically.
5. Prints the public URLs for `web` and `api`.

### 5. Verify

```bash
WEB_URL=$(specific exec web -- printenv | grep ^PUBLIC_URL= | cut -d= -f2)
API_URL=$(specific exec api -- printenv | grep ^PUBLIC_URL= | cut -d= -f2)

curl -s "$API_URL/health"        # → {"status":"ok"}
curl -sI "$WEB_URL/sign-up"      # → 200 OK
```

Then open `$WEB_URL` in a browser, sign up, sign in, upload a 30-90 s clip,
and confirm:
- The upload form polls `/api/jobs/:id`, status flips queued → running → ready.
- The post page shows the highlight; the `<video>` source is a 307 to a
  presigned URL on `storage.media`.

## Custom domain

```bash
specific domain add web app.your-domain.com
# follow the printed DNS instructions
```

Repeat for `api` only if you want the API on a custom host (the browser
hits `web` directly; api is only called server-to-server).

## Operations

### Tail logs

```bash
specific exec web -- npx pino-pretty < /dev/stdout    # or whatever logger
specific exec api -- tail -F /tmp/uvicorn.log         # if you redirect
```

For now both services log to stdout; use the Specific dashboard for live
streaming.

### Re-run schema init manually

The api service does this at startup, but if you ever need to nudge it:

```bash
curl -sS -X POST "$API_URL/schema/init" \
  -H "X-Artemis-Service-Key: $ARTEMIS_API_KEY"
```

### Connect to the database

```bash
specific psql main
```

Drops you into an authenticated `psql` against `postgres.main`. The schema
is the union of every `CREATE TABLE IF NOT EXISTS` / `ALTER TABLE IF NOT
EXISTS` in `src/strava_climbing/db.py:SCHEMA_SQL`.

### Roll back

```bash
specific deploy --environment <previous-env-id>
```

Or use the Specific dashboard's deploy history.

### Preview deploys (per branch)

```bash
specific deploy --preview
```

Spins up an isolated environment off the current worktree. Useful for
reviewing the auth or jobs PRs in production-shaped infra before merging.

## Known caveats

These were called out in `docs/plans/2026-05-28-web-e2e-consumer-app.md`
and not all are fixed yet. As of PR #7:

1. **In-process worker.** Pose processing runs as a FastAPI
   `BackgroundTask` inside the `api` container. If the api restarts mid-job,
   that job stays in `status='running'` forever. The `job` table is already
   shaped for `SELECT ... FOR UPDATE SKIP LOCKED`, so splitting out a
   dedicated `service "worker"` is a non-schema-changing follow-up.
2. **Multipart still buffers through web.** The browser POSTs to `web
   /api/upload` which re-streams to `api /process-upload`. Big files briefly
   pin the web container. Moving to direct-to-S3 presigned PUT is the right
   long-term fix.
3. **Schema migrations are still idempotent DDL, not `specific reshape`.**
   `init_db()` is safe for additive changes but doesn't give you
   zero-downtime column type changes or backfills. Switch to
   `specific reshape` before the first destructive migration.
4. **No structured logging, no Sentry, no rate limits.** All listed in the
   plan; none in scope for this PR.

## Env vars reference

What's actually consumed by the code:

### service "web"

| Var                  | Source                  | Used by                                  |
| -------------------- | ----------------------- | ---------------------------------------- |
| `PORT`               | Specific                | `next start --port $PORT`                |
| `DATABASE_URL`       | `postgres.main.url`     | `lib/db.ts` pg pool                      |
| `ARTEMIS_API_URL`    | `service.api.url`       | `lib/api.ts` for forwarding/proxying     |
| `ARTEMIS_API_KEY`    | `--secret` on deploy    | `lib/api.ts` adds `X-Artemis-Service-Key`|

### service "api"

| Var                  | Source                      | Used by                                |
| -------------------- | --------------------------- | -------------------------------------- |
| `PORT`               | Specific                    | `python -m apps.api`                   |
| `DATABASE_URL`       | `postgres.main.url`         | `strava_climbing.db.connect`           |
| `ARTEMIS_API_KEY`    | `--secret` on deploy        | `_require_service_key` dependency      |
| `ARTEMIS_RAW_DIR`    | HCL literal (`data/raw`)    | `apps/api/main.py` — temp scratch dir  |
| `ARTEMIS_MEDIA_ROOT` | HCL literal (`data`)        | `apps/api/main.py` — local read fallback|
| `S3_ENDPOINT`        | `storage.media.endpoint`    | `strava_climbing.storage_client`       |
| `S3_ACCESS_KEY`      | `storage.media.access_key`  | `strava_climbing.storage_client`       |
| `S3_SECRET_KEY`      | `storage.media.secret_key`  | `strava_climbing.storage_client`       |
| `S3_BUCKET`          | `storage.media.bucket`      | `strava_climbing.storage_client`       |

The only one that you set manually is `ARTEMIS_API_KEY`. Everything else
comes from the HCL or from Specific's resource provisioning.
