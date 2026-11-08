-- Esquema inicial do MVP (seção 6 da especificação).
-- Roda só na primeira subida, quando o volume pgdata está vazio.
-- vec sem dimensão fixa: guarda os vetores separados (EffNet 1280, CLAP 512) e o combinado
-- (1792), que é o escolhido na F2 e tem o índice HNSW parcial.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE tracks (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source      text NOT NULL CHECK (source IN ('fma', 'reccobeats', 'upload')),
    external_id text,
    spotify_id  text,
    title       text,
    artist      text,
    year        int,
    duration_s  real,
    dataset_genre text,          -- rótulo da base (ex.: gênero da FMA), para a avaliação
    audio_sha   char(64),        -- áudio normalizado no S3 (inputs/<sha>.wav)
    license     text,            -- licença do trecho (FMA: Creative Commons)
    created_at  timestamptz DEFAULT now()
);
CREATE UNIQUE INDEX tracks_source_external_id_key ON tracks (source, external_id);

CREATE TABLE track_features (
    track_id         uuid PRIMARY KEY REFERENCES tracks(id) ON DELETE CASCADE,
    key              text,
    scale            text,
    camelot          text,
    key_strength     real,
    bpm              real,
    bpm_confidence   real,
    hihat_density    real,
    subbass_energy   real,
    styles           jsonb,
    genre_top        text,
    vocal_presence   real,
    vocal_gender     text,
    vocal_confidence real
);

CREATE TABLE track_embeddings (
    track_id uuid REFERENCES tracks(id) ON DELETE CASCADE,
    model    text NOT NULL,
    stem     text NOT NULL DEFAULT 'mix',
    vec      vector NOT NULL,
    PRIMARY KEY (track_id, model, stem)
);
CREATE INDEX track_embeddings_effnet_clap_hnsw
    ON track_embeddings USING hnsw ((vec::vector(1792)) vector_cosine_ops)
    WHERE model = 'effnet_clap';

CREATE TABLE jobs (
    id           uuid PRIMARY KEY,
    audio_sha256 char(64) NOT NULL,
    status       text NOT NULL,
    stage        text,
    result       jsonb,
    error        text,
    created_at   timestamptz DEFAULT now(),
    finished_at  timestamptz
);
CREATE INDEX ON jobs (audio_sha256);

CREATE TABLE favorites (
    user_ref   text,
    track_id   uuid REFERENCES tracks(id),
    created_at timestamptz DEFAULT now(),
    PRIMARY KEY (user_ref, track_id)
);

CREATE TABLE spotify_sessions (
    session_id        text PRIMARY KEY,
    spotify_user_id   text NOT NULL,
    display_name      text,
    refresh_token_enc bytea NOT NULL,   -- refresh token criptografado (Fernet)
    created_at        timestamptz DEFAULT now(),
    updated_at        timestamptz DEFAULT now()
);
