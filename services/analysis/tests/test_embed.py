import numpy as np
import pytest

from app.embed import CLAP_SR, chunks, mean_normalized


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [(30, [10, 10, 10]), (25, [10, 10, 5]), (21, [10, 10]), (5, [5]), (1, [1])],
)
def test_chunks(seconds, expected) -> None:
    parts = chunks(np.zeros(seconds * CLAP_SR, dtype=np.float32))
    assert [len(p) // CLAP_SR for p in parts] == expected


def test_mean_normalized() -> None:
    v = mean_normalized(np.array([[3.0, 0.0], [3.0, 8.0]]))
    assert np.linalg.norm(v) == pytest.approx(1.0)
    assert v == pytest.approx([0.6, 0.8])
