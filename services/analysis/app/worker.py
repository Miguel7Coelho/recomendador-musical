import os

from celery import Celery

QUEUE = "analysis"

celery = Celery(
    QUEUE,
    broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
)
celery.conf.update(
    task_default_queue=QUEUE,
    task_soft_time_limit=240,  # avisa a tarefa aos 4 min
    task_time_limit=300,  # mata a tarefa aos 5 min
    task_acks_late=True,  # se o worker cair, a tarefa volta para a fila
    worker_prefetch_multiplier=1,  # pega uma tarefa por vez (Demucs é pesado)
    result_expires=3600,
)


@celery.task(name=f"{QUEUE}.ping")
def ping() -> str:
    return "pong"
