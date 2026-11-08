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

/** O Spotify vem primeiro; o catálogo FMA completa a fila. */
export const spotifyFirst = (catalog: CatalogTrack[], spotify: SpotifyTrack[]): Rec[] => [
  ...spotify.map(fromSpotify),
  ...catalog.map(fromCatalog),
];

export const recTitle = (rec: Rec) => rec.track.title || "Sem título";

export const recArtist = (rec: Rec) =>
  (rec.kind === "catalog" ? rec.track.artist : rec.track.artists.join(", ")) || "Artista desconhecido";
