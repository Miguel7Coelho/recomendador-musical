from pathlib import Path

import essentia.standard as es
import numpy as np

from app import embed, models
from app.features import SR, detect_bpm, detect_key, hihat_density, subbass_energy

STEMS = ("vocals", "drums", "bass", "other")


def _rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(x))))


def _load(path: Path, sr: int) -> np.ndarray:
    return es.MonoLoader(filename=str(path), sampleRate=sr, resampleQuality=4)()


def analyze(mix_path: Path, stem_paths: dict[str, Path]) -> dict:
    """Atributos (formato da tabela track_features) e embeddings de um trecho."""
    mix = _load(mix_path, SR)
    stems = {name: _load(stem_paths[name], SR) for name in STEMS}
    n = min(len(mix), *(len(s) for s in stems.values()))
    mix, stems = mix[:n], {k: v[:n] for k, v in stems.items()}

    harmonic = stems["vocals"] + stems["bass"] + stems["other"]  # tom sem a bateria
    emb_mix = models.embeddings(_load(mix_path, 16000))
    emb_vocals = models.embeddings(_load(stem_paths["vocals"], 16000))

    features = {
        **detect_key(harmonic),
        **detect_bpm(mix),
        "hihat_density": hihat_density(stems["drums"]),
        "subbass_energy": subbass_energy(stems["bass"], mix),
        **models.genre_summary(models.predict(models.GENRE, emb_mix)),
        **models.voice_summary(
            models.predict(models.VOICE, emb_vocals),
            models.predict(models.GENDER, emb_vocals),
            vocal_energy=_rms(stems["vocals"]) / (_rms(mix) or 1.0),
        ),
    }
    effnet = embed.mean_normalized(emb_mix)
    clap = embed.clap_embedding(_load(mix_path, embed.CLAP_SR))
    embeddings = {"effnet": effnet, "clap": clap, "effnet_clap": embed.combined(effnet, clap)}
    return {"features": features, "embeddings": embeddings}
