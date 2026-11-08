import type {
  CatalogRecommendation,
  Features,
  Job,
  Me,
  NewPlaylist,
  RecommendOptions,
  SpotifyMatch,
  SpotifyTrack,
} from "./types";

const BASE = "/api";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function errorMessage(res: Response): Promise<string> {
  const fallback = `Erro ${res.status}`;
  try {
    const body: { detail?: unknown } = await res.json();
    return typeof body.detail === "string" ? body.detail : fallback;
  } catch {
    return fallback;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { credentials: "include", ...init });
  if (!res.ok) throw new ApiError(res.status, await errorMessage(res));
  return res.json() as Promise<T>;
}

function postJson<T>(path: string, body?: unknown): Promise<T> {
  if (body === undefined) return request<T>(path, { method: "POST" });
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export const api = {
  health: () => request<{ status: string; service: string }>("/health"),

  analyze: (file: Blob, filename: string) => {
    const form = new FormData();
    form.append("file", file, filename);
    return request<Job>("/analyze", { method: "POST", body: form });
  },
  job: (jobId: string) => request<Job>(`/jobs/${jobId}`),
  refilter: (jobId: string, options?: RecommendOptions) =>
    postJson<CatalogRecommendation>(`/jobs/${jobId}/recommend`, options),

  moreLikeTrack: (trackId: string, options?: RecommendOptions) =>
    postJson<CatalogRecommendation>(`/recommend/track/${trackId}`, options),
  moreLikeSpotify: (spotifyId: string, seed: Pick<Features, "camelot" | "bpm" | "styles" | "genre_top">) =>
    postJson<{ results: SpotifyTrack[]; relaxed?: string[] }>(`/recommend/spotify/${spotifyId}`, seed),

  matchOnSpotify: (trackId: string) =>
    postJson<{ match: SpotifyMatch | null }>(`/tracks/${trackId}/spotify`),
  me: () => request<Me>("/me"),
  logout: () => postJson<{ ok: boolean }>("/auth/logout"),
  createPlaylist: (playlist: NewPlaylist) =>
    postJson<{ id: string; url: string }>("/playlists", playlist),
};

export const loginUrl = `${BASE}/auth/login`;

/** O gateway devolve caminhos relativos a ele (ex.: /audio/track/{id}). */
export const gatewayUrl = (path: string) => `${BASE}${path}`;
