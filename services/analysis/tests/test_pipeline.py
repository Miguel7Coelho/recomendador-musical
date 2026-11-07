import essentia.standard as es
import numpy as np
import synth

from app import embed, models, pipeline


def write(path, audio) -> None:
    es.MonoWriter(filename=str(path), sampleRate=synth.SR, format="wav")(audio)


def test_analyze_formato_track_features(tmp_path, monkeypatch) -> None:
    harmonic = synth.a_minor_progression()
    n = len(harmonic)
    drums = synth.clicks(120, seconds=n / synth.SR)[:n]
    bass = synth.sine(55, seconds=n / synth.SR)[:n] * 0.3
    mix = harmonic + drums + bass
    paths = {"vocals": harmonic * 0, "drums": drums, "bass": bass, "other": harmonic}
    for name, audio in paths.items():
        write(tmp_path / f"{name}.wav", audio)
    write(tmp_path / "mix.wav", mix)

    monkeypatch.setattr(models, "embeddings", lambda audio: np.zeros((3, 1280), np.float32))
    fake = {
        models.GENRE: {"Pop---Synth-pop": 0.7, "Electronic---House": 0.2},
        models.VOICE: {"instrumental": 0.95, "voice": 0.05},
        models.GENDER: {"female": 0.5, "male": 0.5},
    }
    monkeypatch.setattr(models, "predict", lambda name, emb: fake[name])
    monkeypatch.setattr(embed, "clap_embedding", lambda audio: [0.0] * 512)

    out = pipeline.analyze(tmp_path / "mix.wav", {k: tmp_path / f"{k}.wav" for k in paths})
    r = out["features"]

    assert set(r) == {
        "key", "scale", "camelot", "key_strength", "bpm", "bpm_confidence", "hihat_density",
        "subbass_energy", "styles", "genre_top", "vocal_presence", "vocal_gender",
        "vocal_confidence",
    }  # fmt: skip
    assert r["camelot"] == "8A"
    assert abs(r["bpm"] - 120) < 2
    assert r["genre_top"] == "Pop"
    assert r["subbass_energy"] > 0
    assert len(out["embeddings"]["clap"]) == 512
    assert len(out["embeddings"]["effnet"]) == 1280
