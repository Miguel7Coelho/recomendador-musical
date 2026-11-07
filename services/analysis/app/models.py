"""Classificadores pré-treinados da Essentia (Discogs-EffNet + cabeças de gênero e voz).

Os nomes das camadas de entrada e saída vêm dos .json que acompanham cada modelo, então
trocar de versão do modelo não exige mudar o código.
"""

import json
from functools import cache
from pathlib import Path

import essentia.standard as es
import numpy as np

from app.config import ESSENTIA_MODELS_DIR

EFFNET = "discogs-effnet-bs64-1"
GENRE = "genre_discogs400-discogs-effnet-1"
VOICE = "voice_instrumental-discogs-effnet-1"
GENDER = "gender-discogs-effnet-1"


@cache
def _meta(name: str) -> dict:
    return json.loads((Path(ESSENTIA_MODELS_DIR) / f"{name}.json").read_text())


def _output(meta: dict, purpose: str) -> str:
    return next(o["name"] for o in meta["schema"]["outputs"] if o.get("output_purpose") == purpose)


@cache
def _effnet():
    return es.TensorflowPredictEffnetDiscogs(
        graphFilename=str(Path(ESSENTIA_MODELS_DIR) / f"{EFFNET}.pb"),
        output=_output(_meta(EFFNET), "embeddings"),
    )


@cache
def _head(name: str):
    meta = _meta(name)
    model = es.TensorflowPredict2D(
        graphFilename=str(Path(ESSENTIA_MODELS_DIR) / f"{name}.pb"),
        input=meta["schema"]["inputs"][0]["name"],
        output=_output(meta, "predictions"),
    )
    return model, meta["classes"]


def embeddings(audio_16k: np.ndarray) -> np.ndarray:
    """Embeddings Discogs-EffNet (um vetor de 1280 por janela) de um áudio mono a 16 kHz."""
    return _effnet()(audio_16k)


def predict(name: str, emb: np.ndarray) -> dict[str, float]:
    """Média das ativações por janela de uma cabeça de classificação → {classe: probabilidade}."""
    model, classes = _head(name)
    mean = np.asarray(model(emb)).mean(axis=0)
    return {c: float(p) for c, p in zip(classes, mean)}


def genre_summary(probs: dict[str, float], k: int = 5) -> dict:
    """Top-k estilos do Discogs e o gênero amplo do primeiro (ex.: "Hip Hop---Trap" → "Hip Hop")."""
    top = sorted(probs.items(), key=lambda kv: kv[1], reverse=True)[:k]
    return {
        "styles": {label: round(p, 4) for label, p in top},
        "genre_top": top[0][0].split("---")[0],
    }


def voice_summary(voice: dict[str, float], gender: dict[str, float]) -> dict:
    """Presença de voz e tipo. O filtro de voz só deve usar o tipo quando a presença for alta."""
    label, conf = max(gender.items(), key=lambda kv: kv[1])
    return {"vocal_presence": voice["voice"], "vocal_gender": label, "vocal_confidence": conf}
