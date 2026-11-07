import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def make_tone(tmp_path: Path):
    """Gera um tom senoidal com o ffmpeg (formato e duração escolhidos pelo teste)."""

    def _make(name: str = "tom.mp3", seconds: int = 5, rate: int = 22050) -> Path:
        path = tmp_path / name
        subprocess.run(
            ["ffmpeg", "-nostdin", "-loglevel", "error", "-y",
             "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}:sample_rate={rate}",
             str(path)],
            check=True,
        )  # fmt: skip
        return path

    return _make
