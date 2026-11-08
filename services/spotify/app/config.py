import os

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8000/auth/callback")
# Chave Fernet que criptografa os refresh tokens (gerar com Fernet.generate_key()).
SPOTIFY_TOKEN_KEY = os.getenv("SPOTIFY_TOKEN_KEY", "")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
DATABASE_URL = os.getenv("DATABASE_URL", "").replace("postgresql+psycopg://", "postgresql://")

SCOPES = "playlist-modify-private playlist-modify-public"
