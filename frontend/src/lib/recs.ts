import type { BackupTrack, CatalogTrack, ExternalTrack, SpotifyTrack } from "../api/types";

export type Rec =
  | { kind: "catalog"; key: string; track: CatalogTrack }
  | { kind: "spotify"; key: string; track: SpotifyTrack }
  | { kind: "backup"; key: string; track: BackupTrack };

export const fromCatalog = (track: CatalogTrack): Rec => ({
  kind: "catalog",
  key: `catalog:${track.id}`,
  track,
});

export const fromExternal = (track: ExternalTrack): Rec =>
  track.source === "backup"
    ? { kind: "backup", key: `backup:${track.title}|${track.artists[0]}`, track }
    : { kind: "spotify", key: `spotify:${track.spotify_id}`, track };

/** O Spotify vem primeiro; o catálogo FMA completa a fila. */
export const spotifyFirst = (catalog: CatalogTrack[], spotify: ExternalTrack[]): Rec[] => [
  ...spotify.map(fromExternal),
  ...catalog.map(fromCatalog),
];

export const recTitle = (rec: Rec) => rec.track.title || "Sem título";

export const recArtist = (rec: Rec) =>
  (rec.kind === "catalog" ? rec.track.artist : rec.track.artists.join(", ")) || "Artista desconhecido";
