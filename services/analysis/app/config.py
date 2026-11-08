import os

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

S3_ENDPOINT = os.getenv("S3_ENDPOINT", "http://localhost:8333")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "")
S3_BUCKET = os.getenv("S3_BUCKET", "audio")

ESSENTIA_MODELS_DIR = os.getenv("ESSENTIA_MODELS_DIR", "/models")
# O larger_clap_music gerou vetores colapsados (cos médio 0,95 entre faixas, zero-shot no acaso)
# com o transformers 4.57; o checkpoint geral funciona (ver avaliação da F2).
CLAP_MODEL = os.getenv("CLAP_MODEL", "laion/clap-htsat-unfused")
