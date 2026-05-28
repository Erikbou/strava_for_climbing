build "dashboard" {
  base = "python"
}

service "dashboard" {
  build   = build.dashboard
  command = "streamlit run apps/streamlit/main.py --server.port $PORT --server.address 0.0.0.0 --server.headless true"

  endpoint {
    public = true
    health_check {
      path = "/_stcore/health"
    }
  }

  env = {
    PORT          = port
    DATABASE_URL  = postgres.main.url
    S3_ENDPOINT   = storage.media.endpoint
    S3_ACCESS_KEY = storage.media.access_key
    S3_SECRET_KEY = storage.media.secret_key
    S3_BUCKET     = storage.media.bucket
  }

  dev {
    command = ".venv/bin/streamlit run apps/streamlit/main.py --server.port $PORT --server.address 0.0.0.0 --server.headless true"
  }
}

build "web" {
  base    = "node"
  workdir = "apps/web"
}

service "web" {
  build   = build.web
  command = "pnpm start"

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
    ARTEMIS_MEDIA_ROOT = "../../data"
    S3_ENDPOINT        = storage.media.endpoint
    S3_ACCESS_KEY      = storage.media.access_key
    S3_SECRET_KEY      = storage.media.secret_key
    S3_BUCKET          = storage.media.bucket
  }

  dev {
    command = "pnpm dev"
  }
}

postgres "main" {}

storage "media" {}
