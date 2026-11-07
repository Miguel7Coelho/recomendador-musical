-- Esquema inicial do MVP (seção 6 da especificação).
-- Roda só na primeira subida, quando o volume pgdata está vazio.
-- A dimensão do vetor (512) é a do CLAP; se a F2 escolher o MERT, muda para 768.

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
    created_at  timestamptz DEFAULT now()
);

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
    vec      vector(512) NOT NULL,
    PRIMARY KEY (track_id, model, stem)
);
CREATE INDEX ON track_embeddings USING hnsw (vec vector_cosine_ops);

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
