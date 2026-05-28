## Strava For Climbing

A "Strava for bouldering" demo: per-route leaderboards from raw climbing video. Submitted by team "Island Boys" — Erik Boustedt, Emil Nobrant, Niklavs Visockis, Leonard Xander — for the KTH AI Society hackathon.

### What it does

Drop bouldering videos into `data/raw/`, run the pipeline, open a Streamlit dashboard. The pipeline detects climbers, tracks their pose, segments attempts (start, top, falls, rests), computes time-to-top + smoothness + send/fail per attempt, and displays a per-route leaderboard with side-by-side comparison.

Stage 1 (pose + leaderboard) is the demo. Stage 2 (hold detection + automatic route matching) is optional and isolated — disable with `STRAVA_CLIMBING_DISABLE_STAGE2=1`.

### Quickstart

```bash
uv sync                                    # install core deps
uv sync --extra stage2                     # add optional Stage 2 deps
uv sync --extra dev                        # add dev tooling (pytest, ruff)

# 1. Apply the DB schema in Supabase (Dashboard → SQL Editor):
#    paste supabase/migrations/0001_initial_schema.sql and run it.
# 2. Drop credentials into src/strava_climbing/.env (see .env.example).
# 3. Put videos in data/raw/, then:
uv run strava ingest                       # normalize videos via ffmpeg
uv run strava process                      # pose → attempts → metrics → overlays
uv run streamlit run apps/streamlit/main.py  # open the dashboard
```

### Cloud video storage (optional)

Local-only is the default — videos live under `data/raw/`, `data/normalized/`, and `data/overlays/`. To publish normalized videos to Supabase Storage so a hosted frontend can stream them, create three buckets in Supabase Dashboard → Storage (any names work) and set:

```bash
SUPABASE_STORAGE_RAW_BUCKET=videos-raw
SUPABASE_STORAGE_NORMALIZED_BUCKET=videos-normalized
SUPABASE_STORAGE_OVERLAYS_BUCKET=videos-overlays
```

When the normalized bucket is configured, `strava ingest` uploads each normalized clip after ffmpeg and records the bucket key on the `video` row (`normalized_bucket_key`). The frontend mints a signed URL from that key. Failures are best-effort: the local normalized file remains valid and the failure is logged in `ingest_report.normalized_upload_error`.

For frontend-driven uploads (climber records video → uploads to the raw bucket), run `uv run strava pull-raw` to mirror new bucket files into `data/raw/` before ingesting. To poke at a key, `uv run strava signed-url <key> --kind normalized`.

Apply the migration that adds the bucket-key columns: `supabase/migrations/0002_video_storage_keys.sql`.

### Requirements

- Python 3.12+
- `ffmpeg` ≥ 6.0 on PATH (with `ffprobe`)
- A Supabase project (free tier is fine) — URL + publishable key in `.env`.
  Writes from the pipeline need a `SUPABASE_SERVICE_ROLE_KEY` if you keep RLS enabled.
- A GPU helps but is not required for Stage 1
