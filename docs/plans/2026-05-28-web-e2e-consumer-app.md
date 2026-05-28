# Plan — taking `apps/web` from "ported" to a production E2E consumer app

The Next.js port at `apps/web/` reproduces every Streamlit view and connects
to the same Postgres. To run as a real consumer product on Specific it still
needs accounts, durable uploads, real cloud storage, a worker for the pose
pipeline, schema migrations, and observability. This doc is the punch list,
ordered by what blocks what.

---

## 0. The shape of the current app (so the gaps make sense)

- **Routing**: App Router under `apps/web/app/`. Server components fetch from
  Postgres directly via `pg` (`lib/queries.ts`). Client components only for
  things that need state (`HeroVideo`, `LikeButton`, `UploadForm`, `Chumbox`).
- **Identity**: anonymous `artemis_sid` cookie, minted from a route handler
  the first time the user toggles a kudo. No user record, no auth.
- **Upload**: `POST /api/upload` writes the file under `data/raw/<sha12>.<ext>`
  on the same filesystem, then `spawn`s `scripts/web_upload_harness.py` which
  calls `strava_climbing.orchestrate.process_uploaded_file`. The request
  blocks for the entire pose + render duration.
- **Media playback**: `GET /api/media?path=<abs path>` streams a file off
  disk with byte-range support. Allowed roots come from `ARTEMIS_MEDIA_ROOT`
  (comma-separated). The DB stores **absolute filesystem paths**.
- **Schema**: bootstrapped lazily-once-per-process by `lib/init.ts` shelling
  out to `scripts/web_init_schema.py`, which calls `strava_climbing.db.init_db()`.
- **Specific**: one `web` build + service, sharing `postgres.main` and
  `storage.media`. `storage.media` is declared but **nothing actually
  reads/writes through it** — env vars are piped through and ignored.

---

## 1. Accounts + auth

The single biggest gap. Everything below it depends on `user_id`.

**Schema (new tables / columns)**
- `user(id, email UNIQUE, email_verified_at, password_hash NULL, oauth_provider, oauth_subject, display_name, avatar_url, created_at)`
- `session(id, user_id, expires_at, created_at, user_agent, ip)` — DB-backed sessions so we can revoke
- `climber.user_id` — FK to `user`. Today `climber.name` is free-text typed at upload time; we should let a logged-in user have exactly one `climber` record auto-created.
- `attempt.user_id` — denormalised owner so authz queries don't need a join.

**Flows**
- Sign up: email + password OR OAuth (Google is enough to start; Apple later for iOS). Email verification gated.
- Sign in: same channels. Forgot password (token table, expires_at, single-use).
- Sign out: invalidate the session row.
- Account deletion: soft-delete user, hard-delete sessions, attempts → null user_id (or hard cascade — product call).

**Implementation choice**
Two options:
- **Roll our own** using `bcrypt` (Node) + a `session` table + cookie. Cheap, all in repo, no extra services. Recommended for v1.
- **Use a managed auth provider** (Clerk / WorkOS / Supabase Auth). Faster to ship but adds a vendor and a separate identity store.

Either way the cookie stays an opaque session id; never store JWTs of user data client-side.

**Effort**: 2–3 days for roll-our-own end-to-end including UI, forgot-password
email, and OAuth on top of email/password.

---

## 2. Authorization

With `user_id` in place:
- Upload requires a session.
- Edit / delete a climb requires `attempt.user_id == session.user_id`.
- Kudos require a session (drop the anonymous cookie path).
- Admin role on `user.role = 'admin'` for moderation: hide attempt, ban user.
- Rate limits per session: kudos (e.g. 60/min), uploads (e.g. 5/hour),
  comments (e.g. 30/min). Enforced in middleware with a sliding window
  in Postgres or Redis.

---

## 3. Storage — the path that actually has to change

Today every video is a local-disk file and the DB stores absolute paths.
This is the single biggest deploy blocker.

**What "works on Specific" looks like**
- `storage.media` becomes a real S3-compatible bucket (R2, Tigris, Backblaze
  — Specific marketplace picks one).
- `attempt.highlight_path` and `attempt.overlay_path` store **bucket keys**
  (e.g. `highlights/2026/05/28/<attempt_id>.mp4`), not filesystem paths.
- The pose pipeline writes the rendered video to S3 once, deletes the local
  temp file, stores the key in DB.
- `GET /api/media?key=<key>` returns a 302 to a short-lived presigned URL.
  Or, for small files, streams through — but presigned offloads bandwidth.

**Concrete code changes**
- `src/strava_climbing/storage_client.py` already exists with S3 helpers but
  isn't wired into `orchestrate.py`. Wire it: after `highlight.render(...)`
  succeeds, upload to `S3_BUCKET/highlights/<aid>.mp4`, store the key.
- `src/strava_climbing/db.py` schema: rename `highlight_path` → `highlight_key`
  (with a one-time migration to copy the basename if you want to preserve
  history). Or keep the column name and just change what it contains.
- `apps/web/app/api/media/route.ts`: support `?key=` mode that presigns from
  the same S3 client (port the Python helper to TS, or call `specific exec`
  to mint the URL).
- `data/raw/` becomes ephemeral — files land there only between the upload
  receiving the bytes and the pipeline finishing. Delete after the
  highlight/overlay are uploaded.

**Raw upload size**
The current `bodySizeLimit: "200mb"` in `next.config.ts` works in dev but is
a non-starter in prod: it buffers the whole upload in Node memory. Move to
either:
- **Direct-to-S3 presigned PUT**: client requests a presigned URL from
  `/api/upload/init`, uploads straight to the bucket, then `POST /api/upload/finalize`
  triggers the pipeline by enqueueing a job that points at the S3 key.
- **tus.io resumable uploads** via `@tus/server` — better UX for mobile
  uploads that drop off cellular.

Recommend the presigned PUT flow. Simpler, works on Specific with no extra
services.

---

## 4. Pipeline as a worker, not an HTTP request

Today `/api/upload` `spawn`s Python and blocks the request for the full
processing time. That's wrong for three reasons:
1. Pose detection + render can take 30–120s on a real clip. HTTP timeouts.
2. Multiple uploads serialise on the web container's CPU.
3. Restarting the web container kills in-flight jobs.

**Target architecture**
- New service in `specific.hcl`: `service "worker" { build = build.worker, command = "python -m strava_climbing.worker" }` using `base = "python"` and sharing `postgres.main` + `storage.media`.
- A `job` table: `id, kind, payload jsonb, status, attempts, last_error,
  created_at, started_at, completed_at`. Workers `SELECT ... FOR UPDATE SKIP
  LOCKED` to claim.
- `POST /api/upload` body now: `{ s3_key, climber, color, gym, title }`. It
  inserts a `job` row + an `attempt` row with `status = 'processing'`, returns
  the attempt id. The web user goes straight to `/post/<id>` and sees a
  spinner.
- Worker polls (or LISTEN/NOTIFY) for new jobs, downloads from S3 to local
  tmp, runs orchestrate, uploads results, updates the row to `status = 'ready'`.
- The post page subscribes to a Server-Sent Events endpoint or polls every
  few seconds until the row flips to `ready`, then loads the video.

**Specific specifics**
- Two services share the same Python `.venv`? In containerised deploys each
  build is its own image. The worker image is `base = "python"` and bundles
  the `strava_climbing` package; the web image is `base = "node"`. They don't
  share filesystems — that's why S3 is mandatory.
- `specific docs` should confirm whether long-running services without HTTP
  endpoints are first-class. If not, the worker can expose a trivial `/health`
  and live behind an internal endpoint.

---

## 5. Schema migrations

Today: `strava_climbing.db.init_db()` runs `CREATE TABLE IF NOT EXISTS` + a
handful of `ALTER TABLE ADD COLUMN IF NOT EXISTS`. Fine for dev, dangerous
in prod: no rollback, no audit, no consistency check across boxes.

**Switch to `specific reshape`** (it's in the CLI — `specific reshape
start|complete|status|abort`). Move every DDL into a `migrations/` directory
with numbered files. Reshape does zero-downtime column adds (write to old
and new, then cut over).

For the `web` app's lazy `ensureSchema()`: keep it as a dev convenience,
guard it behind `NODE_ENV !== 'production'`. In prod the deploy pipeline
runs `specific reshape complete` once before the new container takes traffic.

---

## 6. Observability

Currently `console.error` and that's it.

- Structured logging: `pino` in the web app; `structlog` in Python. Include
  request id, user id, attempt id in every line.
- OpenTelemetry: automatic instrumentation in Next.js (built-in), Python
  pipeline emits spans around each stage.
- Error tracking: Sentry on both. Source maps uploaded on deploy.
- Metrics: count uploads/successes/failures, p50/p95 processing time, kudos
  per minute. Specific has an "observability" tab — wire to whatever it
  exposes; Prometheus-compatible is the safe bet.
- Real health endpoint: `/api/health` that checks DB connect and S3 reach,
  returns 503 if either is down. Specific's `health_check.path` should
  point here, not `/`.

---

## 7. Performance + scale

- **Pagination**: feed query returns up to 50 rows unbounded. Add cursor
  pagination (`WHERE (posted_at, id) < (?, ?) ORDER BY posted_at DESC, id
  DESC LIMIT 20`).
- **Caching**: feed page is the hot path. Use Next.js `cache` with a 30s
  revalidate + tag-based invalidation on upload. Or move feed reads to an
  edge function backed by a read replica.
- **Image / video CDN**: videos go through `/api/media` today which means
  every byte hits a Next.js Node process. Move to direct CDN serving:
  bucket → CloudFront/R2 worker → user. The route only mints presigned
  URLs.
- **Database read replicas**: not needed at v1 traffic but the abstraction
  in `lib/db.ts` should make adding a read pool trivial.

---

## 8. Product gaps the design hints at but doesn't have

- **Follow / social graph**: the `Pill tone="neutral">follow</Pill>` on the
  post page doesn't do anything. Need `follow(user_id, target_user_id,
  created_at)` table, follower count, "following" feed scope actually
  filtering by it.
- **Comments**: no schema yet. `comment(id, attempt_id, user_id, body,
  created_at, parent_id NULL)` with nested reply support.
- **Notifications**: real-time-ish bell icon for likes / comments / new
  followers. Table + SSE or websockets.
- **Profile editing**: display name, avatar upload, bio, default gym.
- **Climber↔User linking**: today uploads carry a free-text climber name and
  the pipeline auto-creates a `climber` row. With auth, the upload form
  should pre-fill from `session.user.display_name` and the climber row gets
  linked permanently to the user.
- **Real movement timeline**: post page currently renders a hardcoded
  sparkline + fake chip captions. Pose data has the real jerk-over-time;
  pipe it into a `movement_summary jsonb` column on `attempt` and render
  from that.
- **Empty-state CTAs that work**: "follow" button on profile, "share"
  affordance on post, OG image generation for shared links.

---

## 9. Deploy to Specific — the checklist

In order of "must work" before opening the URL:

1. `specific.hcl` has `build "web" { base = "node", workdir = "apps/web" }`
   ✅ (done).
2. `build "worker" { base = "python" }` + `service "worker"` running the
   pose pipeline as a queue consumer. **Not yet.**
3. `storage.media` actually used by both web (read) and worker (write).
   Today they're declared but unwired. **Not yet.**
4. `postgres.main` has migrations run via `specific reshape complete` as a
   pre-deploy step. Today schema init runs at first DB query — fine in dev,
   should be removed in prod. **Not yet.**
5. Env vars: `DATABASE_URL`, S3 creds — already plumbed through `specific.hcl`.
   Add: `SESSION_COOKIE_SECRET`, `EMAIL_PROVIDER_API_KEY`, `SENTRY_DSN`.
6. Domain: `specific domain` for the custom hostname. HTTPS is automatic.
7. Health check: switch to `/api/health` (real probe) once it exists.
8. CI: GitHub Actions running `npx tsc --noEmit`, `npx next build`, `pytest`
   on every PR. Block merge on red.

**Will paths "just work" on deploy?** No — that's the headline gap. The
upload route's `spawn(pythonBin())` and the media route's filesystem reads
both assume a single host with a `.venv` and a `data/` dir. In a Specific
deploy you get two separate containers (web + worker) and ephemeral disks.
S3 + a queue table is the bridge that makes it work.

---

## 10. Suggested order of attack

1. Lift storage to S3, end-to-end: pipeline writes there, web reads via
   presigned URLs. *(Unblocks deploy.)*
2. Split the worker out of the web container. Add the `job` table. Make
   uploads async. *(Unblocks deploy.)*
3. Switch schema to `specific reshape`. *(Unblocks safe deploys.)*
4. Build auth: sign up, sign in, session, climber↔user link. *(Unblocks
   everything social.)*
5. Wire kudos / upload / edit / delete to the new auth. Drop the anonymous
   cookie.
6. Pagination + edge caching on the feed.
7. Follow + comments + notifications.
8. Observability + Sentry + rate limits.
9. Profile editing + avatar upload.
10. Polish: real movement timeline, OG image generation, mobile PWA manifest.

Each step is ~1–3 days; the auth step is the biggest single chunk. Steps 1–3
have to happen before the URL is shareable; steps 4–5 before it's defensible
as a consumer product; steps 6–10 are quality + growth.
