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
    """Top-k estilos do Discogs e o gênero amplo com a maior soma de probabilidades.

    Somar os estilos de cada gênero ("Funk / Soul---Contemporary R&B", "Funk / Soul---Neo Soul"...)
    é mais estável que olhar só o primeiro estilo quando o modelo está em dúvida.
    """
    top = sorted(probs.items(), key=lambda kv: kv[1], reverse=True)[:k]
    broad: dict[str, float] = {}
    for label, p in probs.items():
        genre = label.split("---")[0]
        broad[genre] = broad.get(genre, 0.0) + p
    return {
        "styles": {label: round(p, 4) for label, p in top},
        "genre_top": max(broad, key=broad.get),
    }


VOICE_THRESHOLD = 0.5


def voice_summary(voice: dict[str, float], gender: dict[str, float]) -> dict:
    """Presença de voz e, só quando ela for alta, o tipo de voz (senão fica vazio)."""
    presence = voice["voice"]
    if presence < VOICE_THRESHOLD:
        return {"vocal_presence": presence, "vocal_gender": None, "vocal_confidence": None}
    label, conf = max(gender.items(), key=lambda kv: kv[1])
    return {"vocal_presence": presence, "vocal_gender": label, "vocal_confidence": conf}
