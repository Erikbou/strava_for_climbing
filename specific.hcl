build "web" {
  base    = "node"
  workdir = "apps/web"
}

service "web" {
  build   = build.web
  command = "cd apps/web && npx next start --port $PORT"

  endpoint {
    public = true
    health_check {
      path = "/"
    }
  }

  env = {
    PORT               = port
    DATABASE_URL       = postgres.main.url
    ARTEMIS_PYTHON     = "../../.venv/bin/python"
    # Comma-separated list of allowed media roots, each resolved against
    # apps/web's cwd. Extend locally (e.g. via your shell env) to whitelist
    # sibling data directories from other worktrees during migration.
    ARTEMIS_MEDIA_ROOT = "../../data"
    S3_ENDPOINT        = storage.media.endpoint
    S3_ACCESS_KEY      = storage.media.access_key
    S3_SECRET_KEY      = storage.media.secret_key
    S3_BUCKET           = storage.media.bucket
  }

  dev {
    command = "cd apps/web && npx next dev --port $PORT --hostname 0.0.0.0"
  }
}

postgres "main" {}

storage "media" {}
