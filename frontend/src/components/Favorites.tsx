import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

import { api, ApiError, loginUrl } from "../api/client";
import { recArtist, recTitle, type Rec } from "../lib/recs";
import { useSession } from "../store";
import { Button, Label, Notice } from "./ui";

const MAX_PLAYLIST_TRACKS = 500;

async function spotifyIdOf(rec: Rec): Promise<string | null> {
  if (rec.kind === "spotify") return rec.track.spotify_id;
  if (rec.kind === "backup") return null; // veio do plano B, sem id do Spotify
  if (rec.track.spotify_id) return rec.track.spotify_id;
  return (await api.matchOnSpotify(rec.track.id)).match?.spotify_id ?? null;
}

type Exported = { url: string | null; missing: string[] };

async function exportPlaylist(name: string, recs: Rec[]): Promise<Exported> {
  const ids = new Set<string>();
  const missing: string[] = [];
  for (const rec of recs) {
    const id = await spotifyIdOf(rec);
    if (id) ids.add(id);
    else missing.push(rec.key);
  }
  if (ids.size === 0) return { url: null, missing };
  const playlist = await api.createPlaylist({ name, spotify_ids: [...ids] });
  return { url: playlist.url, missing };
}

export function Favorites() {
  const { favorites, toggleFavorite } = useSession();
  const [name, setName] = useState("Recomendações");
  const recs = Object.values(favorites);
  const tooMany = recs.length > MAX_PLAYLIST_TRACKS;

  const save = useMutation({
    mutationFn: () => exportPlaylist(name.trim(), recs),
    onError: (error) => {
      // Os favoritos ficam guardados no navegador e sobrevivem à ida ao Spotify.
      if (error instanceof ApiError && error.status === 401) window.location.assign(loginUrl);
    },
  });

  if (recs.length === 0) {
    return <p className="text-muted">Nada por aqui ainda. Favorite uma recomendação para guardá-la.</p>;
  }

  const missing = new Set(save.data?.missing);
  const needsLogin = save.error instanceof ApiError && save.error.status === 401;

  return (
    <div className="space-y-6">
      <ul className="space-y-3">
        {recs.map((rec) => (
          <li key={rec.key} className="well flex items-center justify-between gap-4 px-5 py-3">
            <div className="min-w-0">
              <p className="font-medium break-words">{recTitle(rec)}</p>
              <p className="text-small text-muted">{recArtist(rec)}</p>
              {missing.has(rec.key) && <p className="text-small text-accent">Não está no Spotify</p>}
            </div>
            <Button aria-label={`Remover ${recTitle(rec)}`} onClick={() => toggleFavorite(rec)}>
              Remover
            </Button>
          </li>
        ))}
      </ul>

      <form
        className="space-y-3"
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate();
        }}
      >
        <label className="block">
          <Label>Nome da playlist</Label>
          <input
            required
            maxLength={100}
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="field"
          />
        </label>
        <Button type="submit" variant="primary" disabled={save.isPending || tooMany || !name.trim()}>
          {save.isPending ? "Salvando…" : "Salvar no Spotify"}
        </Button>
      </form>

      {tooMany && <Notice tone="danger">O Spotify aceita até {MAX_PLAYLIST_TRACKS} faixas por vez.</Notice>}
      {save.isError && !needsLogin && <Notice tone="danger">{save.error.message}</Notice>}
      {save.data?.url && (
        <Notice>
          Playlist criada.{" "}
          <a className="text-accent underline" href={save.data.url} target="_blank" rel="noreferrer">
            Abrir no Spotify
          </a>
        </Notice>
      )}
      {save.data && !save.data.url && <Notice>Nenhuma destas faixas está no Spotify, então a playlist não foi criada.</Notice>}
    </div>
  );
}
