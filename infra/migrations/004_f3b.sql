-- F3b: trechos da FMA tocados pelo nosso servidor (com crédito) e login no Spotify.

-- SHA-256 do áudio normalizado (chave inputs/<sha>.wav no S3) e licença Creative Commons.
ALTER TABLE tracks ADD COLUMN IF NOT EXISTS audio_sha char(64);
ALTER TABLE tracks ADD COLUMN IF NOT EXISTS license text;

-- Sessões do Spotify: o refresh token fica só no servidor, criptografado (Fernet).
CREATE TABLE IF NOT EXISTS spotify_sessions (
    session_id        text PRIMARY KEY,
    spotify_user_id   text NOT NULL,
    display_name      text,
    refresh_token_enc bytea NOT NULL,
    created_at        timestamptz DEFAULT now(),
    updated_at        timestamptz DEFAULT now()
);
