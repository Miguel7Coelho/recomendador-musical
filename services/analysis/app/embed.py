"""Embeddings de áudio: CLAP (LAION), EffNet (Essentia) e a combinação dos dois."""

from functools import cache

import numpy as np

from app.config import CLAP_MODEL

CLAP_SR = 48000
CHUNK = 10 * CLAP_SR  # o CLAP vê 10 s por vez


@cache
def _clap():
    from transformers import ClapFeatureExtractor, ClapModel

    model = ClapModel.from_pretrained(CLAP_MODEL).eval()
    return model, ClapFeatureExtractor.from_pretrained(CLAP_MODEL)


def chunks(audio: np.ndarray) -> list[np.ndarray]:
    """Janelas de 10 s; a última só entra se tiver pelo menos 2 s.

    Cortar em janelas fixas evita o corte aleatório que o CLAP faz em áudios longos,
    então o mesmo trecho sempre dá o mesmo vetor.
    """
    parts = [audio[i : i + CHUNK] for i in range(0, len(audio), CHUNK)]
    return [p for p in parts if len(p) >= 2 * CLAP_SR] or parts[:1]


def clap_embedding(audio_48k: np.ndarray) -> list[float]:
    """Média normalizada dos embeddings das janelas (vetor de 512 dimensões)."""
    import torch

    model, extractor = _clap()
    inputs = extractor(chunks(audio_48k), sampling_rate=CLAP_SR, return_tensors="pt")
    with torch.no_grad():
        emb = model.get_audio_features(**inputs).mean(dim=0)
    return (emb / emb.norm()).tolist()


def mean_normalized(frames: np.ndarray) -> list[float]:
    """Média das janelas de um embedding por janela (ex.: Discogs-EffNet), com norma 1."""
    v = np.asarray(frames).mean(axis=0)
    return (v / (np.linalg.norm(v) or 1.0)).astype(float).tolist()


def combined(effnet: list[float], clap: list[float]) -> list[float]:
    """Concatena os dois vetores (já com norma 1) e divide por √2: o resultado tem norma 1 e
    o cosseno entre dois vetores combinados é a média dos cossenos do EffNet e do CLAP.
    Na avaliação da F2 (FMA, 399 faixas) deu precisão@10 de 0,494, contra 0,449 e 0,460.
    """
    v = np.concatenate([effnet, clap]) / np.sqrt(2)
    return v.astype(float).tolist()
