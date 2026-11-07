"""Sinais sintéticos com tom, andamento e ataques conhecidos, para testar os atributos."""

import numpy as np

SR = 44100
RNG = np.random.default_rng(0)


def note(freq: float, seconds: float) -> np.ndarray:
    t = np.arange(int(SR * seconds)) / SR
    wave = sum(np.sin(2 * np.pi * freq * h * t) / h for h in range(1, 6))
    return wave * np.exp(-1.5 * t)


def chord(midis: list[int], seconds: float) -> np.ndarray:
    return sum(note(440 * 2 ** ((m - 69) / 12), seconds) for m in midis)


def a_minor_progression(repeats: int = 4) -> np.ndarray:
    """Lá menor harmônico: Am – Dm – E – Am (o Sol# do acorde de E evita confundir com Dó maior)."""
    bars = [[57, 60, 64], [62, 65, 69], [64, 68, 71], [57, 60, 64]]
    sig = np.concatenate([chord(c, 1.0) for _ in range(repeats) for c in bars])
    return (0.2 * sig / np.max(np.abs(sig))).astype(np.float32)


def clicks(bpm: float, seconds: float = 20.0) -> np.ndarray:
    sig = np.zeros(int(SR * seconds), dtype=np.float32)
    burst = RNG.standard_normal(int(0.03 * SR)) * np.exp(-np.linspace(0, 8, int(0.03 * SR)))
    for start in np.arange(0, seconds, 60 / bpm):
        i = int(start * SR)
        sig[i : i + len(burst)] += burst[: len(sig) - i]
    return 0.5 * sig / np.max(np.abs(sig))


def sine(freq: float, seconds: float = 5.0, amp: float = 0.5) -> np.ndarray:
    t = np.arange(int(SR * seconds)) / SR
    return (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)
