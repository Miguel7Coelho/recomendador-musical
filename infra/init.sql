-- Esquema inicial do MVP (seção 6 da especificação).
-- Roda só na primeira subida, quando o volume pgdata está vazio.
-- Os vetores ficam sem dimensão fixa enquanto a F2 compara modelos (EffNet 1280, CLAP 512);
-- depois da escolha, a dimensão é fixada e o índice HNSW é criado.

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
