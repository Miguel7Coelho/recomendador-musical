from app.worker import celery, ping


def test_queue() -> None:
    assert celery.conf.task_default_queue == "separation"


def test_ping() -> None:
    assert ping.apply().get() == "pong"
