import json

import httpx
import pytest

from app import spotify


class FakeSpotify:
    """Responde às rotas do Spotify usadas pelo serviço e guarda as requisições recebidas."""

    def __init__(self):
        self.calls: list[httpx.Request] = []
        self.search_results: dict[str, list[dict]] = {}

    def __call__(self, req: httpx.Request) -> httpx.Response:
        self.calls.append(req)
        path = req.url.path
        if path == "/api/token":
            form = dict(x.split("=", 1) for x in req.content.decode().split("&"))
            if form["grant_type"] == "client_credentials":
                return httpx.Response(200, json={"access_token": "app", "expires_in": 3600})
            if form["grant_type"] == "authorization_code":
                return httpx.Response(200, json={"access_token": "user", "refresh_token": "r1",
                                                 "expires_in": 3600})  # fmt: skip
            return httpx.Response(200, json={"access_token": "user2", "expires_in": 3600})
        if path == "/v1/me":
            return httpx.Response(200, json={"id": "miguel", "display_name": "Miguel"})
        if path == "/v1/me/playlists":
            return httpx.Response(
                201, json={"id": "pl1", "external_urls": {"spotify": "https://open.spotify.com/x"}}
            )
        if path.startswith("/v1/playlists/") and path.endswith("/items"):
            return httpx.Response(201, json={"snapshot_id": "s"})
        if path == "/v1/search":
            items = self.search_results.get(req.url.params["q"], [])
            return httpx.Response(200, json={"tracks": {"items": items}})
        return httpx.Response(404)

    def bodies(self, suffix: str) -> list[dict]:
        return [json.loads(c.content) for c in self.calls if c.url.path.endswith(suffix)]


@pytest.fixture
def fake(monkeypatch):
    f = FakeSpotify()
    monkeypatch.setattr(spotify, "client", lambda: httpx.Client(transport=httpx.MockTransport(f)))
    spotify._app_token.update(value=None, expires=0.0)
    return f


def track(tid: str, name: str, *artists: str) -> dict:
    return {"id": tid, "name": name, "artists": [{"name": a} for a in artists],
            "external_urls": {"spotify": f"https://open.spotify.com/track/{tid}"}}  # fmt: skip
