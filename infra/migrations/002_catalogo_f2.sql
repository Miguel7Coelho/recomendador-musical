-- F2: catálogo para a avaliação dos embeddings.
-- Rode uma vez num banco criado com o init.sql antigo (o init.sql novo já inclui isto).

-- Rótulo da base de dados (ex.: gênero da FMA), usado para medir a precisão@k.
ALTER TABLE tracks ADD COLUMN IF NOT EXISTS dataset_genre text;

-- Evita gravar a mesma faixa da FMA duas vezes (permite retomar a carga).
CREATE UNIQUE INDEX IF NOT EXISTS tracks_source_external_id_key ON tracks (source, external_id);

-- Vetores sem dimensão fixa: o EffNet tem 1280 e o CLAP 512, e os dois ficam na mesma
-- tabela enquanto a F2 compara. Depois da escolha, a dimensão é fixada e o índice HNSW volta.
DROP INDEX IF EXISTS track_embeddings_vec_idx;
ALTER TABLE track_embeddings ALTER COLUMN vec TYPE vector;
