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

### Requirements

- Python 3.12+
- `ffmpeg` ≥ 6.0 on PATH (with `ffprobe`)
- A Supabase project (free tier is fine) — URL + publishable key in `.env`.
  Writes from the pipeline need a `SUPABASE_SERVICE_ROLE_KEY` if you keep RLS enabled.
- A GPU helps but is not required for Stage 1
