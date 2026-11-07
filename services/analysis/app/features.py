"""Atributos musicais calculados por processamento de sinal (sem modelos treinados)."""

import essentia
import essentia.standard as es
import numpy as np

essentia.log.infoActive = False
essentia.log.warningActive = False

SR = 44100

# Roda de Camelot: número + A (menor) / B (maior). Nomes no formato que a Essentia devolve.
_CAMELOT_MINOR = ["Ab", "Eb", "Bb", "F", "C", "G", "D", "A", "E", "B", "F#", "C#"]
_CAMELOT_MAJOR = ["B", "F#", "C#", "Ab", "Eb", "Bb", "F", "C", "G", "D", "A", "E"]
_ENHARMONIC = {"Db": "C#", "D#": "Eb", "Gb": "F#", "G#": "Ab", "A#": "Bb"}


def camelot(key: str, scale: str) -> str:
    key = _ENHARMONIC.get(key, key)
    wheel, letter = (_CAMELOT_MINOR, "A") if scale == "minor" else (_CAMELOT_MAJOR, "B")
    return f"{wheel.index(key) + 1}{letter}"


def detect_key(harmonic: np.ndarray) -> dict:
    """Tom medido sem a bateria (voz + baixo + outros), como na seção 4 da especificação."""
    key, scale, strength = es.KeyExtractor(sampleRate=SR)(harmonic)
    return {
        "key": key,
        "scale": scale,
        "camelot": camelot(key, scale),
        "key_strength": float(strength),
    }


def detect_bpm(mix: np.ndarray) -> dict:
    bpm, _, confidence, _, _ = es.RhythmExtractor2013(method="multifeature")(mix)
    # A confiança do método multifeature vai de 0 a ~5,32; normalizamos para 0–1.
    return {"bpm": float(bpm), "bpm_confidence": float(min(confidence / 5.32, 1.0))}


def hihat_density(drums: np.ndarray) -> float:
    """Ataques por segundo na faixa de 6 a 12 kHz da stem de bateria."""
    band = es.LowPass(cutoffFrequency=12000, sampleRate=SR)(
        es.HighPass(cutoffFrequency=6000, sampleRate=SR)(drums)
    )
    _, rate = es.OnsetRate()(band)
    return float(rate)


def subbass_energy(bass: np.ndarray, mix: np.ndarray, cutoff_hz: float = 80.0) -> float:
    """Fração da energia total da mixagem que está no baixo abaixo de ~80 Hz."""
    total = float(np.sum(np.abs(np.fft.rfft(mix)) ** 2))
    if total == 0.0:
        return 0.0
    spectrum = np.abs(np.fft.rfft(bass)) ** 2
    freqs = np.fft.rfftfreq(len(bass), 1 / SR)
    return float(np.sum(spectrum[freqs < cutoff_hz]) / total)
