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

postgres "main" {}

storage "media" {}
