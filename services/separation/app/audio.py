import hashlib
import subprocess
from pathlib import Path

from app.config import MAX_EXCERPT_SECONDS, MIN_SECONDS


class InvalidAudio(Exception):
    pass


def normalize(src: Path, dst: Path) -> None:
    """Converte qualquer formato que o ffmpeg decodifique em WAV 44,1 kHz estéreo, cortado."""
    cmd = [
        "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(src),
        "-vn", "-t", str(MAX_EXCERPT_SECONDS),
        "-ac", "2", "-ar", "44100", "-c:a", "pcm_s16le",
        str(dst),
    ]  # fmt: skip
    result = subprocess.run(cmd, capture_output=True, text=True)
    # Cabeçalho WAV tem 44 bytes: abaixo disso não sobrou áudio nenhum.
    if result.returncode != 0 or not dst.exists() or dst.stat().st_size <= 44:
        raise InvalidAudio(result.stderr.strip() or "arquivo sem áudio")
    seconds = (dst.stat().st_size - 44) / (44100 * 2 * 2)  # 44,1 kHz, 16 bits, estéreo
    if seconds < MIN_SECONDS:
        raise InvalidAudio(f"áudio muito curto ({seconds:.1f} s; mínimo {MIN_SECONDS} s)")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
