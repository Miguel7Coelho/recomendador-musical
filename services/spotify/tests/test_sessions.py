"""Sessões contra um Postgres de verdade (só com TEST_DATABASE_URL; APAGA o schema public)."""

import os
from pathlib import Path

import psycopg
import pytest
from cryptography.fernet import Fernet

from app import sessions

URL = os.getenv("TEST_DATABASE_URL")
INIT_SQL = Path(__file__).resolve().parents[3] / "infra" / "init.sql"
pytestmark = pytest.mark.skipif(not URL, reason="TEST_DATABASE_URL não definido")


@pytest.fixture
def db(monkeypatch):
    with psycopg.connect(URL, autocommit=True) as admin:
        admin.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
        admin.execute(INIT_SQL.read_text())
    monkeypatch.setattr(sessions, "DATABASE_URL", URL)
    monkeypatch.setattr(sessions, "SPOTIFY_TOKEN_KEY", Fernet.generate_key().decode())
    sessions._fernet.cache_clear()
    sessions._access.clear()
    yield
    sessions._fernet.cache_clear()


def test_refresh_token_criptografado_e_girado(db, monkeypatch) -> None:
    sessions.save("s1", "miguel", "Miguel", {"access_token": "a1", "refresh_token": "segredo",
                                             "expires_in": 3600})  # fmt: skip
    with psycopg.connect(URL) as c:
        enc = bytes(c.execute("SELECT refresh_token_enc FROM spotify_sessions").fetchone()[0])
    assert b"segredo" not in enc  # nunca em texto puro no banco
    assert sessions.get("s1") == {"spotify_user_id": "miguel", "display_name": "Miguel"}
    assert sessions.access_token("s1") == "a1"  # do cache

    sessions._access.clear()  # simula reinício do serviço
    seen = []
    novo = {"access_token": "a2", "refresh_token": "novo", "expires_in": 1}
    monkeypatch.setattr(sessions.spotify, "refresh", lambda rt: seen.append(rt) or novo)
    assert sessions.access_token("s1") == "a2" and seen == ["segredo"]
    sessions._access.clear()
    assert sessions.access_token("s1") == "a2" and seen == ["segredo", "novo"]  # girou

    sessions.delete("s1")
    assert sessions.get("s1") is None and sessions.access_token("s1") is None
