import os

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

S3_ENDPOINT = os.getenv("S3_ENDPOINT", "http://localhost:8333")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "")
S3_BUCKET = os.getenv("S3_BUCKET", "audio")

DEMUCS_MODEL = os.getenv("DEMUCS_MODEL", "htdemucs")
TORCH_DEVICE = os.getenv("TORCH_DEVICE", "auto")  # auto | cpu | cuda
MAX_EXCERPT_SECONDS = int(os.getenv("MAX_EXCERPT_SECONDS", "30"))
MIN_SECONDS = 3  # abaixo disso os classificadores não geram nenhuma janela de análise

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
STEMS = ("vocals", "drums", "bass", "other")
