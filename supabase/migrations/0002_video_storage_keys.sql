-- Cloud video storage references for the video table.
-- Applied via Supabase Dashboard → SQL Editor (or `supabase db push`).
--
-- Both columns are nullable. A row may have:
--   - source_path + normalized_path only (local-only ingest)
--   - source_path + normalized_path + normalized_bucket_key (locally normalized,
--     published to Supabase Storage)
--   - all four columns (raw uploaded via the frontend, normalized published)
--
-- The frontend reads normalized_bucket_key (+ overlay_bucket_key on attempt,
-- added later) and mints signed URLs via storage.signed_url().

alter table video
  add column if not exists source_bucket_key text,
  add column if not exists normalized_bucket_key text;

create unique index if not exists video_normalized_bucket_key_uniq
  on video (normalized_bucket_key)
  where normalized_bucket_key is not null;

create unique index if not exists video_source_bucket_key_uniq
  on video (source_bucket_key)
  where source_bucket_key is not null;
