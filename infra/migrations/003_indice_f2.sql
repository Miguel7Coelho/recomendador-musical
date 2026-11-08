-- F2 (fechamento): o embedding escolhido é a combinação EffNet + CLAP (1792 dimensões).
-- Índice HNSW parcial só para esse modelo. A coluna vec segue sem dimensão fixa para guardar
-- também os vetores separados (effnet, clap) usados na avaliação.
CREATE INDEX IF NOT EXISTS track_embeddings_effnet_clap_hnsw
    ON track_embeddings USING hnsw ((vec::vector(1792)) vector_cosine_ops)
    WHERE model = 'effnet_clap';
