# Recomendador musical por análise de áudio

TCC · Ciência da Computação · UNIP · 2026

## Subir o ambiente

```bash
cp .env.example .env      # preencher as senhas e as chaves do Spotify
docker compose up -d --build
docker compose ps         # todos "healthy" (o s3 aparece só como "running")
```

## Serviços

| Serviço | Porta (localhost) |
|---|---|
| gateway | 8000 |
| separation-api | 8001 |
| analysis-api | 8002 |
| catalog-api | 8003 |
| spotify-api | 8004 |
| PostgreSQL + pgvector | 5432 |
| Redis | 6379 |
| S3 (SeaweedFS) | 8333 · painel em 23646 |

Todos respondem em `GET /health`.

## Front-end

```bash
cd frontend
npm install
npm run dev               # abrir http://127.0.0.1:5173 (nunca localhost)
```

O visual segue `frontend/DESIGN.md`.

## Testes de um serviço

```bash
cd services/gateway
uv run pytest
```

## Publicação

O frontend fica no Cloudflare Pages e o backend na máquina local, exposto por um Cloudflare Tunnel.
A função `frontend/functions/api/[[path]].js` repassa `/api/*` ao gateway, então site e API ficam na
mesma origem e nenhuma porta precisa ser aberta.

```bash
# Backend: mantenha rodando enquanto o site estiver no ar
docker compose up -d
cloudflared tunnel --url http://127.0.0.1:8000

# Frontend
cd frontend && npm run build
npx wrangler pages deploy dist --project-name recomendador-musical
npx wrangler pages secret put BACKEND_URL --project-name recomendador-musical
```

Com o endereço do site definido, ajuste o `.env` e recrie os serviços com `docker compose up -d`:

```bash
FRONTEND_URL=https://SEU-SITE
COOKIE_SECURE=true
SPOTIFY_REDIRECT_URI=https://SEU-SITE/api/auth/callback
```

Cadastre o mesmo `SPOTIFY_REDIRECT_URI` no painel do app do Spotify.
