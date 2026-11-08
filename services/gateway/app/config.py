import os

SEPARATION_URL = os.getenv("SEPARATION_URL", "http://separation-api:8000")
ANALYSIS_URL = os.getenv("ANALYSIS_URL", "http://analysis-api:8000")
CATALOG_URL = os.getenv("CATALOG_URL", "http://catalog-api:8000")
SPOTIFY_API_URL = os.getenv("SPOTIFY_API_URL", "http://spotify-api:8000")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

S3_ENDPOINT = os.getenv("S3_ENDPOINT", "http://localhost:8333")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "")
S3_BUCKET = os.getenv("S3_BUCKET", "audio")

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://127.0.0.1:5173")
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"  # true em produção (HTTPS)
EMBEDDING_MODEL = "effnet_clap"
