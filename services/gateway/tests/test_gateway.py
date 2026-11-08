import io
import json
import uuid

import httpx
import pytest
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient

import app.main as main
from app import clients

SHA = "a" * 64
FMA_ID = str(uuid.uuid4())
UPLOAD_ID = str(uuid.uuid4())
FEATURES = {"camelot": "11A", "bpm": 100.0, "styles": {"Pop---Synth-pop": 0.5}}
VEC = [0.1] * 4


class Services:
    """Separação, análise, catálogo e spotify-api falsos. `plan` controla cada cenário."""

    def __init__(self, sep_cached=True, ana_cached=True, sep_polls=1, ana_polls=1,
                 ana_fails=False, external_ok=True, sep_status=202,
                 external_relaxed=None):  # fmt: skip
        self.external_relaxed = external_relaxed
        self.sep_cached, self.ana_cached = sep_cached, ana_cached
        self.sep_left, self.ana_left = sep_polls, ana_polls
        self.ana_fails, self.external_ok, self.sep_status = ana_fails, external_ok, sep_status
        self.calls: list[httpx.Request] = []

    def __call__(self, req: httpx.Request) -> httpx.Response:
        self.calls.append(req)
        host, path = req.url.host, req.url.path
        analysis = {"features": FEATURES, "embeddings": {"effnet_clap": VEC, "clap": [0.0]}}
        if host == "separation-api":
            if path == "/separate":
                if self.sep_status == 400:
                    return httpx.Response(400, json={"detail": "Áudio inválido: áudio muito curto"})
                if self.sep_cached:
                    return httpx.Response(200, json={"status": "done", "cached": True, "sha": SHA})
                return httpx.Response(202, json={"status": "queued", "job_id": "sj", "sha": SHA})
            self.sep_left -= 1
            status = "done" if self.sep_left < 0 else "started"
            return httpx.Response(200, json={"status": status})
        if host == "analysis-api":
            if path == "/analyze":
                if self.ana_cached:
                    return httpx.Response(200, json={"status": "done", **analysis})
                return httpx.Response(202, json={"status": "queued", "job_id": "aj", "sha": SHA})
            self.ana_left -= 1
            if self.ana_left < 0:
                if self.ana_fails:
                    return httpx.Response(200, json={"status": "failed", "error": "boom"})
                return httpx.Response(200, json={"status": "done", **analysis})
            return httpx.Response(200, json={"status": "started"})
        if host == "catalog-api":
            if path == "/recommend":
                assert json.loads(req.content)["vec"] == VEC
                rows = [{"id": FMA_ID, "source": "fma", "audio_sha": SHA, "artist": "AWOL",
                         "license": "CC BY 4.0"},
                        {"id": UPLOAD_ID, "source": "upload", "audio_sha": SHA}]  # fmt: skip
                return httpx.Response(200, json={"results": rows, "relaxed": ["key: exact → off"]})
            if path == "/recommend/external":
                if not self.external_ok:
                    return httpx.Response(502, json={"detail": "fora"})
                out = {"results": [{"spotify_id": "s1"}]}
                if self.external_relaxed:
                    out["relaxed"] = self.external_relaxed
                return httpx.Response(200, json=out)
            if path == f"/tracks/{FMA_ID}":
                return httpx.Response(200, json={"id": FMA_ID, "source": "fma", "audio_sha": SHA,
                                                 "title": "Food", "artist": "AWOL"})  # fmt: skip
            if path == f"/tracks/{UPLOAD_ID}":
                return httpx.Response(200, json={"id": UPLOAD_ID, "source": "upload",
                                                 "audio_sha": SHA})  # fmt: skip
        if host == "spotify-api":
            if path == "/auth/url":
                return httpx.Response(200, json={"url": "https://accounts.spotify.com/authorize?x"})
            if path == "/auth/exchange":
                return httpx.Response(200, json={"session_id": "sess-123", "display_name": "M"})
            if path in ("/me", "/playlists"):
                if req.headers.get("X-Session") != "sess-123":
                    return httpx.Response(401, json={"detail": "Faça login no Spotify"})
                return httpx.Response(200, json={"ok": path})
            if path == "/match":
                return httpx.Response(200, json={"match": {"spotify_id": "m1"}})
            if path == "/auth/logout":
                return httpx.Response(200, json={"ok": True})
        return httpx.Response(404, json={"detail": f"rota falsa ausente: {host}{path}"})


class FakeStore:
    def __init__(self):
        self.data = {}

    def setex(self, key, ttl, value):
        self.data[key] = value

    def get(self, key):
        return self.data.get(key)


@pytest.fixture
def setup(monkeypatch):
    def make(**plan):
        svc = Services(**plan)
        http = httpx.Client(transport=httpx.MockTransport(svc))
        monkeypatch.setattr(clients, "http", lambda: http)
        monkeypatch.setattr(clients, "store", lambda: FakeStore.instance)
        return TestClient(main.app), svc

    FakeStore.instance = FakeStore()
    return make


def upload(c):
    return c.post("/analyze", files={"file": ("x.mp3", b"audio", "audio/mpeg")})


def test_tudo_em_cache_responde_na_hora(setup) -> None:
    c, svc = setup()
    r = upload(c)
    assert r.status_code == 202
    body = r.json()
    assert body["status"] == "done" and body["features"] == FEATURES
    catalog = body["result"]["catalog"]
    assert catalog[0]["audio_url"] == f"/audio/track/{FMA_ID}"
    assert catalog[0]["credit"] == "AWOL · CC BY 4.0"
    assert "audio_url" not in catalog[1]  # áudio enviado por usuário nunca é servido
    assert body["result"]["spotify"] == [{"spotify_id": "s1"}]
    assert "vec" not in json.dumps(body)  # o embedding não vai para o front


def test_maquina_de_estados(setup) -> None:
    # O próprio POST /analyze já faz a 1ª consulta à separação.
    c, svc = setup(sep_cached=False, ana_cached=False, sep_polls=2, ana_polls=2)
    job = upload(c).json()
    assert job["status"] == "separating"
    get = lambda: c.get(f"/jobs/{job['job_id']}").json()  # noqa: E731
    assert get()["status"] == "separating"  # 1ª consulta: Demucs ainda rodando
    assert get()["status"] == "analyzing"  # separou e já enfileirou a análise
    assert get()["status"] == "analyzing"
    done = get()
    assert done["status"] == "done" and done["result"]["relaxed"] == ["key: exact → off"]


def test_falha_na_analise(setup) -> None:
    c, _ = setup(ana_cached=False, ana_polls=0, ana_fails=True)
    job = upload(c).json()
    out = c.get(f"/jobs/{job['job_id']}").json()
    assert out["status"] == "failed" and out["error"] == "análise: boom"


def test_spotify_fora_nao_derruba_o_catalogo(setup) -> None:
    c, _ = setup(external_ok=False)
    body = upload(c).json()
    assert body["status"] == "done" and len(body["result"]["catalog"]) == 2
    assert body["result"]["spotify"] == [] and "spotify_error" in body["result"]


def test_relaxamento_do_spotify_chega_ao_front(setup) -> None:
    c, _ = setup(external_relaxed=["key: compatible → off"])
    result = upload(c).json()["result"]
    assert result["spotify_relaxed"] == ["key: compatible → off"]
    assert result["relaxed"] == ["key: exact → off"]  # o do catálogo continua separado


def test_erro_da_separacao_e_repassado(setup) -> None:
    c, _ = setup(sep_status=400)
    r = upload(c)
    assert r.status_code == 400 and "muito curto" in r.json()["detail"]


def test_job_inexistente(setup) -> None:
    c, _ = setup()
    assert c.get(f"/jobs/{uuid.uuid4()}").status_code == 404


def test_refiltrar_reaproveita_a_analise_do_job(setup) -> None:
    c, svc = setup()
    job = upload(c).json()
    svc.calls.clear()
    filters = {"key": "compatible", "locked": ["voice"], "bpm_min": 90}
    # Quem chama não consegue trocar a consulta guardada no job.
    options = {"filters": filters, "k": 5, "vec": [9.9], "features": {}, "model": "clap"}
    r = c.post(f"/jobs/{job['job_id']}/recommend", json=options)
    assert r.status_code == 200
    body = r.json()
    assert body["relaxed"] == ["key: exact → off"]
    assert body["results"][0]["audio_url"] == f"/audio/track/{FMA_ID}"
    assert "audio_url" not in body["results"][1]
    assert [x.url.path for x in svc.calls] == ["/recommend"]  # nada de reanalisar
    sent = json.loads(svc.calls[0].content)
    assert sent == {**options, "vec": VEC, "features": FEATURES, "model": "effnet_clap"}


def test_refiltrar_sem_corpo_usa_os_padroes(setup) -> None:
    c, svc = setup()
    job = upload(c).json()
    svc.calls.clear()
    assert c.post(f"/jobs/{job['job_id']}/recommend").status_code == 200
    sent = json.loads(svc.calls[0].content)
    assert sent == {"vec": VEC, "features": FEATURES, "model": "effnet_clap"}


def test_refiltrar_job_inexistente_ou_sem_analise(setup) -> None:
    c, svc = setup(sep_cached=False, sep_polls=5)
    assert c.post(f"/jobs/{uuid.uuid4()}/recommend").status_code == 404
    job = upload(c).json()
    assert job["status"] == "separating"
    assert c.post(f"/jobs/{job['job_id']}/recommend").status_code == 409


def test_refiltrar_com_catalogo_fora(setup, monkeypatch) -> None:
    c, _ = setup()
    job = upload(c).json()

    def catalog_down(req):
        raise httpx.ConnectError("catálogo reiniciando")

    monkeypatch.setattr(
        clients, "http", lambda: httpx.Client(transport=httpx.MockTransport(catalog_down))
    )
    assert c.post(f"/jobs/{job['job_id']}/recommend").status_code == 503


def test_audio_so_da_fma(setup, monkeypatch) -> None:
    c, _ = setup()

    class Body(io.BytesIO):
        def iter_chunks(self):
            yield self.getvalue()

    fake_s3 = type("S3", (), {"get_object": lambda self, **kw: {
        "Body": Body(b"RIFFwav"), "ContentLength": 7, "key": kw["Key"]}})()  # fmt: skip
    monkeypatch.setattr(clients, "s3", lambda: fake_s3)
    r = c.get(f"/audio/track/{FMA_ID}")
    assert r.status_code == 200 and r.content == b"RIFFwav"
    assert r.headers["content-type"] == "audio/wav"
    assert c.get(f"/audio/track/{UPLOAD_ID}").status_code == 404


def test_audio_aceita_range_para_pular_na_faixa(setup, monkeypatch) -> None:
    c, _ = setup()
    seen = {}

    class Body(io.BytesIO):
        def iter_chunks(self):
            yield self.getvalue()

    def get_object(**kw):
        seen.clear()
        seen.update(kw)
        if kw.get("Range") == "bytes=99-":
            error = {"Error": {"Code": "InvalidRange"}}
            raise ClientError(error, "GetObject")
        if "Range" in kw:
            return {"Body": Body(b"FFw"), "ContentLength": 3, "ContentRange": "bytes 2-4/7"}
        return {"Body": Body(b"RIFFwav"), "ContentLength": 7}

    monkeypatch.setattr(
        clients, "s3", lambda: type("S3", (), {"get_object": staticmethod(get_object)})()
    )
    url = f"/audio/track/{FMA_ID}"

    r = c.get(url, headers={"Range": "bytes=2-4"})
    assert r.status_code == 206 and r.content == b"FFw"
    assert r.headers["content-range"] == "bytes 2-4/7" and r.headers["accept-ranges"] == "bytes"

    assert c.get(url, headers={"Range": "bytes=99-"}).status_code == 416

    r = c.get(url, headers={"Range": "bytes=0-1,3-4"})  # vários intervalos: arquivo inteiro
    assert r.status_code == 200 and "Range" not in seen and r.headers["accept-ranges"] == "bytes"


def test_login_e_sessao(setup) -> None:
    c, svc = setup()
    r = c.get("/auth/login", follow_redirects=False)
    assert r.status_code == 307 and r.headers["location"].startswith("https://accounts.spotify")

    r = c.get("/auth/callback", params={"code": "c", "state": "s"}, follow_redirects=False)
    assert r.headers["location"] == "http://127.0.0.1:5173/?login=ok"
    cookie = r.headers["set-cookie"]
    assert "session=sess-123" in cookie and "HttpOnly" in cookie and "SameSite=lax" in cookie

    r = c.get("/auth/callback", params={"error": "access_denied"}, follow_redirects=False)
    assert r.headers["location"].endswith("?login=cancelado")

    c.cookies.clear()
    assert c.get("/me").status_code == 401  # sem cookie
    c.cookies.set("session", "sess-123")
    assert c.get("/me").json() == {"ok": "/me"}
    body = {"name": "x", "spotify_ids": ["a"]}
    assert c.post("/playlists", json=body).json() == {"ok": "/playlists"}


def test_correspondencia_e_mais_parecidas(setup) -> None:
    c, svc = setup()
    assert c.post(f"/tracks/{FMA_ID}/spotify").json() == {"match": {"spotify_id": "m1"}}
    r = c.post("/recommend/spotify/abc", json={"camelot": "8A", "bpm": 90}).json()
    assert r == {"results": [{"spotify_id": "s1"}]}
    sent = json.loads(next(x for x in svc.calls if x.url.path == "/recommend/external").content)
    assert sent == {"features": {"camelot": "8A", "bpm": 90}, "exclude_spotify_ids": ["abc"]}


def test_servico_reiniciando_nao_perde_o_upload(setup, monkeypatch) -> None:
    c, svc = setup()
    real = svc.__call__

    def catalog_down_once(req):
        if req.url.host == "catalog-api" and not getattr(svc, "_down", False):
            svc._down = True
            raise httpx.ConnectError("catálogo reiniciando")
        return real(req)

    monkeypatch.setattr(
        clients, "http", lambda: httpx.Client(transport=httpx.MockTransport(catalog_down_once))
    )
    r = upload(c)
    assert r.status_code == 202 and r.json()["status"] == "searching"  # parou na busca
    assert c.get(f"/jobs/{r.json()['job_id']}").json()["status"] == "done"  # e continuou
