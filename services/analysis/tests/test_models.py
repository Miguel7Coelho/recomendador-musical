import json

import numpy as np
import pytest

from app import models


def test_genre_summary() -> None:
    probs = {"Hip Hop---Trap": 0.6, "Pop---Indie Pop": 0.3, "Electronic---House": 0.05,
             "Rock---Punk": 0.01, "Jazz---Bop": 0.02, "Funk / Soul---Soul": 0.04}  # fmt: skip
    r = models.genre_summary(probs, k=3)
    assert list(r["styles"]) == ["Hip Hop---Trap", "Pop---Indie Pop", "Electronic---House"]
    assert r["genre_top"] == "Hip Hop"


def test_genre_amplo_pela_soma() -> None:
    # Um estilo eletrônico na frente, mas três de Funk / Soul somando mais.
    probs = {"Electronic---Downtempo": 0.13, "Funk / Soul---Contemporary R&B": 0.10,
             "Funk / Soul---Neo Soul": 0.08, "Funk / Soul---Soul": 0.05}  # fmt: skip
    r = models.genre_summary(probs)
    assert next(iter(r["styles"])) == "Electronic---Downtempo"
    assert r["genre_top"] == "Funk / Soul"


def test_voice_summary() -> None:
    r = models.voice_summary(
        {"instrumental": 0.1, "voice": 0.9}, {"female": 0.8, "male": 0.2}, vocal_energy=0.4
    )
    assert r == {"vocal_presence": 0.9, "vocal_gender": "female", "vocal_confidence": 0.8}


def test_instrumental_sem_tipo_de_voz() -> None:
    r = models.voice_summary(
        {"instrumental": 0.58, "voice": 0.42}, {"female": 0.7, "male": 0.3}, vocal_energy=0.4
    )
    assert r == {"vocal_presence": 0.42, "vocal_gender": None, "vocal_confidence": None}


def test_stem_de_voz_muda_e_instrumental() -> None:
    # Caso real: stem de voz com 0,5% da energia da mixagem e classificador em 0,9 por vazamento.
    r = models.voice_summary(
        {"instrumental": 0.1, "voice": 0.9}, {"female": 0.7, "male": 0.3}, vocal_energy=0.005
    )
    assert r == {"vocal_presence": 0.0, "vocal_gender": None, "vocal_confidence": None}


@pytest.fixture
def fake_models(tmp_path, monkeypatch):
    """Grava .json no formato oficial e troca o TensorflowPredict2D por um modelo falso."""
    head = {
        "classes": ["instrumental", "voice"],
        "schema": {
            "inputs": [{"name": "model/Placeholder"}],
            "outputs": [
                {"name": "model/Softmax", "output_purpose": "predictions"},
                {"name": "model/dense/BiasAdd", "output_purpose": ""},
            ],
        },
    }
    (tmp_path / f"{models.VOICE}.json").write_text(json.dumps(head))
    created = {}

    def fake_predict2d(**kwargs):
        created.update(kwargs)
        return lambda emb: np.array([[0.2, 0.8], [0.4, 0.6]], dtype=np.float32)

    monkeypatch.setattr(models, "ESSENTIA_MODELS_DIR", str(tmp_path))
    monkeypatch.setattr(models.es, "TensorflowPredict2D", fake_predict2d)
    models._meta.cache_clear()
    models._head.cache_clear()
    yield created
    models._meta.cache_clear()
    models._head.cache_clear()


def test_predict_le_camadas_do_json_e_faz_media(fake_models) -> None:
    probs = models.predict(models.VOICE, np.zeros((2, 1280), dtype=np.float32))
    assert probs == pytest.approx({"instrumental": 0.3, "voice": 0.7})
    assert fake_models["input"] == "model/Placeholder"
    assert fake_models["output"] == "model/Softmax"
