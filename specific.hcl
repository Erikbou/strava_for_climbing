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
    PORT             = port
    DATABASE_URL     = postgres.main.url
    # Internal URL of the api service. The web app proxies uploads + schema
    # bootstrap and 302s media requests here.
    ARTEMIS_API_URL  = service.api.url
    # Shared secret. Set the same value on both services in production via
    # `specific env`; locally it can be left empty (the api treats empty as
    # "open mode" for dev convenience).
    ARTEMIS_API_KEY  = ""
  }

  dev {
    command = "cd apps/web && npx next dev --port $PORT --hostname 0.0.0.0"
  }
}

build "api" {
  base = "python"
}

service "api" {
  build   = build.api
  command = "python -m apps.api"

  endpoint {
    public = true
    health_check {
      path = "/health"
    }
  }

  env = {
    PORT               = port
    DATABASE_URL       = postgres.main.url
    ARTEMIS_API_KEY    = ""
    ARTEMIS_MEDIA_ROOT = "data"
    ARTEMIS_RAW_DIR    = "data/raw"
    S3_ENDPOINT        = storage.media.endpoint
    S3_ACCESS_KEY      = storage.media.access_key
    S3_SECRET_KEY      = storage.media.secret_key
    S3_BUCKET          = storage.media.bucket
  }

  dev {
    command = ".venv/bin/python -m apps.api"
  }
}

postgres "main" {}

storage "media" {}
