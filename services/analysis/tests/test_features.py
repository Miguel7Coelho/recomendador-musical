import pytest
import synth

from app.features import camelot, detect_bpm, detect_key, hihat_density, subbass_energy


@pytest.mark.parametrize(
    ("key", "scale", "code"),
    [("F#", "minor", "11A"), ("C#", "minor", "12A"), ("A", "minor", "8A"), ("Ab", "minor", "1A"),
     ("A", "major", "11B"), ("C", "major", "8B"), ("B", "major", "1B"),
     ("Db", "major", "3B"), ("G#", "minor", "1A")],
)  # fmt: skip
def test_camelot(key, scale, code) -> None:
    assert camelot(key, scale) == code


def test_camelot_cobre_as_24_tonalidades() -> None:
    names = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
    codes = {camelot(k, s) for k in names for s in ("major", "minor")}
    assert len(codes) == 24


def test_tom_la_menor() -> None:
    k = detect_key(synth.a_minor_progression())
    assert (k["key"], k["scale"], k["camelot"]) == ("A", "minor", "8A")
    assert 0 <= k["key_strength"] <= 1


@pytest.mark.parametrize("bpm", [90, 120, 140])
def test_bpm(bpm) -> None:
    r = detect_bpm(synth.clicks(bpm))
    assert r["bpm"] == pytest.approx(bpm, abs=1)
    assert 0 <= r["bpm_confidence"] <= 1


@pytest.mark.parametrize("rate", [4, 8])
def test_hihat_density(rate) -> None:
    assert hihat_density(synth.clicks(rate * 60)) == pytest.approx(rate, abs=0.5)


def test_subbass() -> None:
    mix = synth.sine(50) + synth.sine(1000)
    assert subbass_energy(synth.sine(50), mix) == pytest.approx(0.5, abs=0.05)
    assert subbass_energy(synth.sine(1000), mix) == pytest.approx(0, abs=1e-6)
    assert subbass_energy(synth.sine(50), synth.sine(50) * 0) == 0.0
