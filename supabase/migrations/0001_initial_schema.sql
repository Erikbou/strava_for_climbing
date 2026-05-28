-- Strava-for-climbing initial schema.
-- Apply via Supabase Dashboard → SQL Editor (or `supabase db push` if using the CLI).
-- Translated from src/strava_climbing/schema.py (SQLite) to PostgreSQL.

create table if not exists climber (
  id      bigint generated always as identity primary key,
  name    text not null,
  aliases jsonb not null default '[]'::jsonb
);
create unique index if not exists climber_name_lower_uniq on climber (lower(name));

create table if not exists video (
  id               bigint generated always as identity primary key,
  source_path      text not null,
  normalized_path  text not null unique,
  source_sha256    text not null unique,
  duration_seconds double precision not null check (duration_seconds > 0),
  width            integer not null check (width > 0),
  height           integer not null check (height > 0),
  fps              double precision not null check (fps > 0),
  ingest_status    text not null check (ingest_status in ('pending','ok','rejected','error')),
  ingest_report    jsonb
);

create table if not exists wall (
  id                bigint generated always as identity primary key,
  gym_name          text not null,
  sample_frame_path text,
  dinov3_embedding  bytea
);

create table if not exists route (
  id                 bigint generated always as identity primary key,
  wall_id            bigint not null references wall(id) on delete restrict,
  color              text,
  sample_frame_path  text,
  hold_layout        jsonb,
  layout_embedding   bytea,
  origin             text not null check (origin in ('manual','auto','unassigned')),
  cluster_confidence double precision check (cluster_confidence is null
                                             or cluster_confidence between 0 and 1)
);

create table if not exists attempt (
  id              bigint generated always as identity primary key,
  climber_id      bigint references climber(id) on delete set null,
  route_id        bigint references route(id)   on delete set null,
  video_id        bigint not null references video(id) on delete cascade,
  start_frame     integer not null check (start_frame >= 0),
  end_frame       integer not null check (end_frame > start_frame),
  time_seconds    double precision not null check (time_seconds > 0),
  smoothness_raw  double precision,
  smoothness_pct  double precision check (smoothness_pct is null
                                          or smoothness_pct between 0 and 100),
  send            boolean not null,
  attempts_count  integer not null check (attempts_count >= 1),
  route_source    text not null check (route_source in ('manual','auto','unassigned')),
  overlay_path    text unique,
  config_hash     text not null,
  unique (video_id, start_frame, end_frame)
);

create table if not exists hold (
  id        bigint generated always as identity primary key,
  wall_id   bigint not null references wall(id)  on delete cascade,
  route_id  bigint          references route(id) on delete set null,
  x         double precision not null check (x between 0 and 1),
  y         double precision not null check (y between 0 and 1),
  w         double precision not null check (w > 0),
  h         double precision not null check (h > 0),
  color_hsv jsonb
);

create index if not exists idx_attempt_route_send_time
  on attempt(route_id, send desc, time_seconds asc);
create index if not exists idx_attempt_climber on attempt(climber_id);
create index if not exists idx_attempt_video   on attempt(video_id);
create index if not exists idx_route_origin    on route(origin);
create index if not exists idx_route_wall      on route(wall_id);
create index if not exists idx_hold_wall_route on hold(wall_id, route_id);

-- Manual route assignments are sticky: Stage-2 auto-clustering must never
-- overwrite a human-confirmed pairing. Application-level guard lives in
-- src/strava_climbing/provenance.py::transition() — this trigger is the
-- DB-level second line of defense.
create or replace function protect_manual_route() returns trigger
language plpgsql as $$
begin
  if old.route_source = 'manual' and new.route_source <> 'manual' then
    raise exception 'cannot overwrite manual route assignment';
  end if;
  return new;
end;
$$;

drop trigger if exists trg_attempt_protect_manual on attempt;
create trigger trg_attempt_protect_manual
  before update of route_id, route_source on attempt
  for each row execute function protect_manual_route();

-- Convenience view: route list with attempt count, ordered to match the
-- old SQLite `list_routes()` ORDER BY clause.
create or replace view route_with_attempt_counts as
  select r.id,
         r.color,
         r.origin,
         r.sample_frame_path,
         r.cluster_confidence,
         r.wall_id,
         count(a.id) as attempt_count
    from route r
    left join attempt a on a.route_id = r.id
   group by r.id;

-- RLS is OFF for these tables by default when created via the SQL editor.
-- For production, enable RLS and add policies appropriate for your roles:
--   alter table attempt enable row level security;
--   create policy "service role full access" on attempt
--     for all to service_role using (true) with check (true);
