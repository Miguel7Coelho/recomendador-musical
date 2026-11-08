import type { CatalogTrack, SpotifyTrack } from "../api/types";

export type Rec =
  | { kind: "catalog"; key: string; track: CatalogTrack }
  | { kind: "spotify"; key: string; track: SpotifyTrack };

export const fromCatalog = (track: CatalogTrack): Rec => ({
  kind: "catalog",
  key: `catalog:${track.id}`,
  track,
});

export const fromSpotify = (track: SpotifyTrack): Rec => ({
  kind: "spotify",
  key: `spotify:${track.spotify_id}`,
  track,
});

/** Alterna as duas fontes, começando pelo catálogo (análise completa e áudio próprio). */
export function interleave(catalog: CatalogTrack[], spotify: SpotifyTrack[]): Rec[] {
  const out: Rec[] = [];
  for (let i = 0; i < Math.max(catalog.length, spotify.length); i++) {
    const c = catalog[i];
    const s = spotify[i];
    if (c) out.push(fromCatalog(c));
    if (s) out.push(fromSpotify(s));
  }
  return out;
}

export const recTitle = (rec: Rec) => rec.track.title || "Sem título";

export const recArtist = (rec: Rec) =>
  (rec.kind === "catalog" ? rec.track.artist : rec.track.artists.join(", ")) || "Artista desconhecido";
