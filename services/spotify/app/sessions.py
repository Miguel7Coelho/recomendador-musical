"""Sessões do Spotify: refresh token criptografado no Postgres, access token em memória."""

import time
from functools import cache

import psycopg
from cryptography.fernet import Fernet

from app import spotify
from app.config import DATABASE_URL, SPOTIFY_TOKEN_KEY

_access: dict[str, tuple[str, float]] = {}  # session_id → (access token, expira em)


@cache
def _fernet() -> Fernet:
    return Fernet(SPOTIFY_TOKEN_KEY)


def _connect() -> psycopg.Connection:
    return psycopg.connect(DATABASE_URL)


def save(session_id: str, user_id: str, name: str | None, tokens: dict) -> None:
    enc = _fernet().encrypt(tokens["refresh_token"].encode())
    with _connect() as conn:
        conn.execute(
            """INSERT INTO spotify_sessions (session_id, spotify_user_id, display_name,
                                             refresh_token_enc)
               VALUES (%s, %s, %s, %s)""",
            (session_id, user_id, name, enc),
        )
    _access[session_id] = (tokens["access_token"], time.time() + tokens["expires_in"])


def get(session_id: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT spotify_user_id, display_name FROM spotify_sessions WHERE session_id = %s",
            (session_id,),
        ).fetchone()
    return {"spotify_user_id": row[0], "display_name": row[1]} if row else None


def delete(session_id: str) -> None:
    _access.pop(session_id, None)
    with _connect() as conn:
        conn.execute("DELETE FROM spotify_sessions WHERE session_id = %s", (session_id,))


def access_token(session_id: str) -> str | None:
    cached = _access.get(session_id)
    if cached and time.time() < cached[1] - 60:
        return cached[0]
    with _connect() as conn:
        row = conn.execute(
            "SELECT refresh_token_enc FROM spotify_sessions WHERE session_id = %s", (session_id,)
        ).fetchone()
        if row is None:
            return None
        tokens = spotify.refresh(_fernet().decrypt(bytes(row[0])).decode())
        if "refresh_token" in tokens:  # o Spotify pode girar o refresh token
            conn.execute(
                """UPDATE spotify_sessions SET refresh_token_enc = %s, updated_at = now()
                   WHERE session_id = %s""",
                (_fernet().encrypt(tokens["refresh_token"].encode()), session_id),
            )
    _access[session_id] = (tokens["access_token"], time.time() + tokens["expires_in"])
    return tokens["access_token"]
