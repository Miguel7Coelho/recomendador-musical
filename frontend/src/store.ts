import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { Rec } from "./lib/recs";

type Session = {
  /** Guardado para sobreviver ao retorno do login do Spotify; o job expira em 2 h. */
  jobId: string | null;
  favorites: Record<string, Rec>;
  autoplay: boolean;
  setJob: (jobId: string | null) => void;
  toggleFavorite: (rec: Rec) => void;
  toggleAutoplay: () => void;
};

export const useSession = create<Session>()(
  persist(
    (set) => ({
      jobId: null,
      favorites: {},
      autoplay: false,
      setJob: (jobId) => set({ jobId }),
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
