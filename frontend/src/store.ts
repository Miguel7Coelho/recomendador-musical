import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { Song } from "./api/types";
import type { Rec } from "./lib/recs";

type Session = {
  /** Guardado para sobreviver ao retorno do login do Spotify; o job expira em 2 h. */
  jobId: string | null;
  /** Música pesquisada sem áudio; exclui o job e vice-versa. */
  song: Song | null;
  favorites: Record<string, Rec>;
  autoplay: boolean;
  setJob: (jobId: string | null) => void;
  searchSong: (song: Song) => void;
  reset: () => void;
  toggleFavorite: (rec: Rec) => void;
  toggleAutoplay: () => void;
};

export const useSession = create<Session>()(
  persist(
    (set) => ({
      jobId: null,
      song: null,
      favorites: {},
      autoplay: false,
      setJob: (jobId) => set({ jobId, song: null }),
      searchSong: (song) => set({ song, jobId: null }),
      reset: () => set({ jobId: null, song: null }),
      toggleFavorite: (rec) =>
        set(({ favorites }) => {
          const { [rec.key]: existing, ...rest } = favorites;
          return { favorites: existing ? rest : { ...favorites, [rec.key]: rec } };
        }),
      toggleAutoplay: () => set(({ autoplay }) => ({ autoplay: !autoplay })),
    }),
    { name: "recomendador-sessao" },
  ),
);
