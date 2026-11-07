from pathlib import Path
from tempfile import TemporaryDirectory

from celery import Celery

from app.config import REDIS_URL
from app.storage import analysis_key, download, exists, get_json, input_key, put_json, stem_keys

QUEUE = "analysis"

celery = Celery(QUEUE, broker=REDIS_URL, backend=REDIS_URL)
celery.conf.update(
    task_default_queue=QUEUE,
    task_soft_time_limit=240,  # avisa a tarefa aos 4 min
    task_time_limit=300,  # mata a tarefa aos 5 min
    task_acks_late=True,  # se o worker cair, a tarefa volta para a fila
    task_track_started=True,  # GET /analyze/{id} mostra "started" enquanto roda
    worker_prefetch_multiplier=1,
    result_expires=3600,
)


class StemsMissing(Exception):
    pass


@celery.task(name=f"{QUEUE}.ping")
def ping() -> str:
    return "pong"


@celery.task(name=f"{QUEUE}.analyze")
def analyze(sha: str) -> dict:
    cached = get_json(analysis_key(sha))
    if cached is not None:
        return {"sha": sha, **cached, "cached": True}

    keys = stem_keys(sha)
    if not all(exists(k) for k in keys.values()):
        raise StemsMissing(f"Stems de {sha} não encontradas: rode a separação antes")

    from app.pipeline import analyze as run  # importado aqui: carrega Essentia/TensorFlow

    with TemporaryDirectory() as tmp:
        mix = Path(tmp) / "mix.wav"
        download(input_key(sha), mix)
        stems = {}
        for stem, key in keys.items():
            stems[stem] = Path(tmp) / f"{stem}.wav"
            download(key, stems[stem])
        result = run(mix, stems)

    put_json(analysis_key(sha), result)
    return {"sha": sha, **result, "cached": False}
