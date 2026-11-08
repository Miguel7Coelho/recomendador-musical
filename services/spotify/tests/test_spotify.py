import base64
import hashlib
from urllib.parse import parse_qs, urlparse

from conftest import track

from app import spotify


def test_pkce() -> None:
    verifier, challenge = spotify.new_pkce()
    expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=")
    assert challenge == expected.decode() and 43 <= len(verifier) <= 128


def test_authorize_url() -> None:
    q = parse_qs(urlparse(spotify.authorize_url("st", "ch")).query)
    assert q["code_challenge_method"] == ["S256"] and q["code_challenge"] == ["ch"]
    assert q["state"] == ["st"] and q["response_type"] == ["code"]
    assert q["scope"] == ["playlist-modify-private playlist-modify-public"]
    assert q["redirect_uri"] == ["http://127.0.0.1:8000/auth/callback"]


def test_normalize() -> None:
    assert spotify.normalize("Beyoncé – Halo (feat. X) [Remastered]") == "beyonce halo"


def test_match_exige_titulo_e_artista(fake) -> None:
    fake.search_results["track:Food artist:AWOL"] = [
        track("x1", "Food", "Outro Artista"),
        track("x2", "Food (Live)", "AWOL", "Convidado"),
    ]
    m = spotify.match("Food", "AWOL")
    assert m["spotify_id"] == "x2" and m["artists"] == ["AWOL", "Convidado"]
    assert spotify.match("Nada", "Ninguém") is None


def test_genre_seeds_com_fallback(fake) -> None:
    fake.search_results["downtempo"] = [track("a", "A", "x"), track("b", "B", "y")]
    assert spotify.genre_seeds("downtempo") == ["a", "b"]  # genre: vazio → busca por texto


def test_token_do_app_e_reaproveitado(fake) -> None:
    spotify.search_tracks("x")
    spotify.search_tracks("y")
    assert sum(c.url.path == "/api/token" for c in fake.calls) == 1


def test_playlist_em_lotes_de_100(fake) -> None:
    spotify.add_items("tok", "pl1", [f"id{i}" for i in range(150)])
    lotes = fake.bodies("/items")
    assert [len(b["uris"]) for b in lotes] == [100, 50]
    assert lotes[0]["uris"][0] == "spotify:track:id0"
