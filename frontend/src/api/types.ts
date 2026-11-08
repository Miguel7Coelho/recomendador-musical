// Contrato do gateway (docs/resumo_projeto.json).

export type Features = {
  key: string;
  scale: "major" | "minor";
  camelot: string;
  key_strength: number;
  bpm: number;
  bpm_confidence: number;
  hihat_density: number;
  subbass_energy: number;
  styles: Record<string, number>;
  genre_top: string;
  vocal_presence: number;
  vocal_gender: "female" | "male" | null;
  vocal_confidence: number | null;
};

export type ScoreComponents = {
  cosine: number;
  key: number;
  genre: number;
  voice: number;
};

export type CatalogTrack = {
  id: string;
  source: "fma" | "upload";
  external_id: string | null;
  spotify_id: string | null;
  title: string | null;
  artist: string | null;
  year: number | null;
  dataset_genre: string | null;
  camelot: string;
  key: string;
  scale: "major" | "minor";
  bpm: number;
  styles: Record<string, number>;
  genre_top: string;
  vocal_presence: number;
  vocal_gender: "female" | "male" | null;
  vocal_confidence: number | null;
  license: string | null;
  audio_sha: string | null;
  cosine: number;
  score: number;
  components: ScoreComponents;
  explanation: string;
  audio_url?: string;
  credit?: string;
};

export type SpotifyTrack = {
  source: "lastfm";
  spotify_id: string;
  title: string;
  artists: string[];
  url: string;
  camelot: string;
  bpm: number;
  explanation: string;
};

export type JobResult = {
  catalog: CatalogTrack[];
  relaxed: string[];
  spotify: SpotifyTrack[];
  spotify_relaxed?: string[];
  spotify_error?: string;
};

export type JobStatus = "separating" | "analyzing" | "searching" | "done" | "failed";

export type Job = {
  job_id: string;
  status: JobStatus;
  sha: string;
  features?: Features;
  result?: JobResult;
  error?: string;
};

export type Filters = {
  key?: "exact" | "compatible" | "off";
  genre?: "style" | "genre" | "off";
  voice?: "on" | "off";
  locked?: Array<"key" | "genre" | "voice">;
  bpm_min?: number;
  bpm_max?: number;
  year_min?: number;
  year_max?: number;
};

export type RecommendOptions = {
  filters?: Filters;
  k?: number;
  min_candidates?: number;
  pool?: number;
  exclude_ids?: string[];
  weights?: ScoreComponents;
};

export type CatalogRecommendation = {
  results: CatalogTrack[];
  levels: unknown;
  relaxed: string[];
  pool: number;
};

export type SpotifyMatch = { spotify_id: string } & Record<string, unknown>;

export type Me = { spotify_user_id: string; display_name: string | null };

export type NewPlaylist = { name: string; spotify_ids: string[]; public?: boolean };
