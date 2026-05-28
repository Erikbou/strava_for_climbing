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

# Put videos in data/raw/, then:
uv run strava init-db                      # create local DB / print Supabase steps
uv run strava ingest                       # normalize videos via ffmpeg
uv run strava process                      # pose → attempts → metrics → overlays
uv run streamlit run apps/streamlit/main.py  # open the dashboard
```

### Persistence: Supabase or fully local

The pipeline has two interchangeable backends. The choice is made at import
time by `config.runtime.use_supabase()`:

- **Supabase** — Postgres for relational data, Supabase Storage for the .mp4
  renders. Activated automatically when `NEXT_PUBLIC_SUPABASE_URL` (or
  `SUPABASE_URL`) is set, or force it with `STRAVA_CLIMBING_BACKEND=supabase`.
  Apply `supabase/migrations/0001_initial_schema.sql` in the Supabase SQL
  editor (or `supabase db push`); it also provisions the `normalized` and
  `overlays` public buckets. Pipeline writes need `SUPABASE_SERVICE_ROLE_KEY`
  in `src/strava_climbing/.env` if you keep RLS on.
- **Local** — SQLite at `data/climbing.sqlite` + plain files under
  `data/normalized/` and `data/overlays/`. Activated when no Supabase URL is
  configured, or force it with `STRAVA_CLIMBING_BACKEND=sqlite`. No network,
  no credentials, no migrations to apply — useful for offline work and CI.

DB columns `video.normalized_path` and `attempt.overlay_path` always store
the object key (a basename like `abc123.mp4`); the backend resolves it to a
public URL or a local `Path` so the Streamlit dashboard works in either mode.

### Requirements

- Python 3.12+
- `ffmpeg` ≥ 6.0 on PATH (with `ffprobe`)
- A GPU helps but is not required for Stage 1
- Optional: a Supabase project (free tier is fine). Without it, everything
  runs locally against SQLite.
