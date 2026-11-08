import pytest

import app.worker as worker
from app.worker import StemsMissing, celery, ping

RESULT = {"features": {"camelot": "8A", "bpm": 120.0}, "embeddings": {"clap": [0.1]}}


def test_queue() -> None:
    assert celery.conf.task_default_queue == "analysis"


def test_ping() -> None:
    assert ping.apply().get() == "pong"


def test_usa_cache(monkeypatch) -> None:
    monkeypatch.setattr(worker, "get_json", lambda key: RESULT)
    r = worker.analyze.apply(args=["abc"]).get()
    assert r == {"sha": "abc", **RESULT, "cached": True}


def test_sem_stems(monkeypatch) -> None:
    monkeypatch.setattr(worker, "get_json", lambda key: None)
    monkeypatch.setattr(worker, "exists", lambda key: False)
    with pytest.raises(StemsMissing):
        worker.analyze.apply(args=["abc"]).get()


def test_analisa_e_grava(monkeypatch) -> None:
    saved = {}
    monkeypatch.setattr(worker, "get_json", lambda key: None)
    monkeypatch.setattr(worker, "exists", lambda key: True)
    monkeypatch.setattr(worker, "download", lambda key, path: path.write_bytes(b""))
    monkeypatch.setattr(worker, "put_json", lambda key, data: saved.update({key: data}))
    monkeypatch.setattr("app.pipeline.analyze", lambda mix, stems: RESULT)
    r = worker.analyze.apply(args=["abc"]).get()
    assert r["cached"] is False
    assert saved == {"analysis/v2/abc.json": RESULT}
