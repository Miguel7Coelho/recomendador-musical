import json
import subprocess
from pathlib import Path

import pytest

from app.audio import InvalidAudio, normalize, sha256


def probe(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    )  # fmt: skip
    data = json.loads(out.stdout)
    return {**data["streams"][0], "duration": float(data["format"]["duration"])}


def test_normalize_formato_e_corte(make_tone, tmp_path: Path) -> None:
    dst = tmp_path / "out.wav"
    normalize(make_tone(seconds=45), dst)
    info = probe(dst)
    assert info["sample_rate"] == "44100"
    assert info["channels"] == 2
    assert info["codec_name"] == "pcm_s16le"
    assert info["duration"] == pytest.approx(30, abs=0.1)


def test_normalize_rejeita_lixo(tmp_path: Path) -> None:
    src = tmp_path / "lixo.mp3"
    src.write_bytes(b"isto nao e audio" * 100)
    with pytest.raises(InvalidAudio):
        normalize(src, tmp_path / "out.wav")


def test_sha256_estavel(make_tone, tmp_path: Path) -> None:
    src = make_tone()
    a, b = tmp_path / "a.wav", tmp_path / "b.wav"
    normalize(src, a)
    normalize(src, b)
    assert sha256(a) == sha256(b)
    assert len(sha256(a)) == 64
