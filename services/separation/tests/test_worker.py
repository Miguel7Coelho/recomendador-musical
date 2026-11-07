from pathlib import Path

import app.worker as worker
from app.worker import celery, ping


def test_queue() -> None:
    assert celery.conf.task_default_queue == "separation"


def test_ping() -> None:
    assert ping.apply().get() == "pong"


def test_separate_envia_quatro_stems(monkeypatch) -> None:
    uploads = []
    monkeypatch.setattr(worker, "stems_cached", lambda sha: False)
    monkeypatch.setattr(worker, "download", lambda key, path: path.write_bytes(b"wav"))

    def fake_demucs(src: Path, outdir: Path) -> Path:
        out = outdir / "htdemucs"
        out.mkdir(parents=True)
        for stem in ("vocals", "drums", "bass", "other"):
            (out / f"{stem}.wav").write_bytes(b"stem")
        return out

    monkeypatch.setattr(worker, "run_demucs", fake_demucs)
    monkeypatch.setattr(worker, "upload", lambda path, key: uploads.append((path.name, key)))

    result = worker.separate.apply(args=["abc"]).get()
    assert result["cached"] is False
    assert sorted(uploads) == sorted(
        (f"{s}.wav", f"stems/abc/{s}.wav") for s in ("vocals", "drums", "bass", "other")
    )


def test_separate_usa_cache(monkeypatch) -> None:
    monkeypatch.setattr(worker, "stems_cached", lambda sha: True)
    monkeypatch.setattr(worker, "download", lambda *a: (_ for _ in ()).throw(AssertionError))
    assert worker.separate.apply(args=["abc"]).get()["cached"] is True
