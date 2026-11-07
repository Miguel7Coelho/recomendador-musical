import os

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

S3_ENDPOINT = os.getenv("S3_ENDPOINT", "http://localhost:8333")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "")
S3_BUCKET = os.getenv("S3_BUCKET", "audio")

ESSENTIA_MODELS_DIR = os.getenv("ESSENTIA_MODELS_DIR", "/models")
