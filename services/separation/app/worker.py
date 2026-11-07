import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from celery import Celery

from app.config import DEMUCS_MODEL, REDIS_URL, TORCH_DEVICE
from app.storage import download, input_key, stem_keys, stems_cached, upload

QUEUE = "separation"

celery = Celery(QUEUE, broker=REDIS_URL, backend=REDIS_URL)
celery.conf.update(
    task_default_queue=QUEUE,
    task_soft_time_limit=240,  # avisa a tarefa aos 4 min
    task_time_limit=300,  # mata a tarefa aos 5 min
    task_acks_late=True,  # se o worker cair, a tarefa volta para a fila
    task_track_started=True,  # GET /separate/{id} mostra "started" enquanto roda
    worker_prefetch_multiplier=1,  # pega uma tarefa por vez (Demucs é pesado)
    result_expires=3600,
)


@celery.task(name=f"{QUEUE}.ping")
def ping() -> str:
    return "pong"


@celery.task(name=f"{QUEUE}.separate")
def separate(sha: str) -> dict:
    keys = stem_keys(sha)
    if stems_cached(sha):
        return {"sha": sha, "stems": keys, "cached": True}

    with TemporaryDirectory() as tmp:
        src = Path(tmp) / "input.wav"
        download(input_key(sha), src)
        out = run_demucs(src, Path(tmp) / "out")
        for stem, key in keys.items():
            upload(out / f"{stem}.wav", key)

    return {"sha": sha, "stems": keys, "cached": False}


def run_demucs(src: Path, outdir: Path) -> Path:
    """Roda o Demucs e devolve a pasta com vocals/drums/bass/other.wav."""
    cmd = [
        sys.executable, "-m", "demucs.separate",
        "-n", DEMUCS_MODEL, "-d", _device(),
        "-o", str(outdir), "--filename", "{stem}.{ext}",
        str(src),
    ]  # fmt: skip
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=230)
    if result.returncode != 0:
        raise RuntimeError(f"Demucs falhou: {result.stderr.strip()[-2000:]}")
    return outdir / DEMUCS_MODEL


def _device() -> str:
    if TORCH_DEVICE != "auto":
        return TORCH_DEVICE
    import torch  # importado aqui para a API não carregar o torch à toa

    return "cuda" if torch.cuda.is_available() else "cpu"
