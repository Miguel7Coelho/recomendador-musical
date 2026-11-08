import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { api } from "../api/client";
import type { Song } from "../api/types";
import { Button, Label } from "./ui";

const DEBOUNCE_MS = 300;

type SongFieldProps = {
  initialQuery: string;
  value: Song | null;
  onChange: (song: Song | null) => void;
  /** Sem áudio escolhido, a música pesquisada já é o ponto de partida. */
  onSearch?: (song: Song) => void;
};

export function SongField({ initialQuery, value, onChange, onSearch }: SongFieldProps) {
  const [query, setQuery] = useState(initialQuery);
  const [debounced, setDebounced] = useState(initialQuery);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(query.trim()), DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [query]);

  // Se a busca falhar, o campo só fica sem sugestões: ele é opcional.
  const songs = useQuery({
    queryKey: ["songs", debounced],
    queryFn: () => api.searchSongs(debounced),
    enabled: !value && debounced.length >= 2,
    retry: false,
    staleTime: Infinity,
  });

  if (value) {
    return (
      <div>
        <Label>Música</Label>
        <div className="well mt-2 flex items-center justify-between gap-4 px-5 py-3">
          <div className="min-w-0">
            <p className="font-medium break-words">{value.title}</p>
            <p className="text-small text-muted">{value.artist}</p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {onSearch && (
              <Button variant="primary" onClick={() => onSearch(value)}>
                Procurar
              </Button>
            )}
            <button
              type="button"
              aria-label="Limpar música"
              onClick={() => onChange(null)}
              className="flex size-8 cursor-pointer items-center justify-center rounded-full text-muted transition-colors duration-200 hover:text-accent"
            >
              <svg viewBox="0 0 16 16" className="size-3 stroke-current" strokeWidth={2} aria-hidden>
                <path d="M2 2l12 12M14 2L2 14" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    );
  }

  const results = songs.data?.results ?? [];
  return (
    <div>
      <label className="block">
        <Label>Ou pesquise uma música</Label>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Artista e nome da música"
          autoComplete="off"
          className="field"
        />
      </label>
      <p className="mt-2 text-small text-muted">
        Encontramos faixas parecidas pelo que os ouvintes dela também escutam.
      </p>
      {results.length > 0 && (
        <ul className="well mt-3 p-2" aria-label="Sugestões">
          {results.map((song) => (
            <li key={`${song.title}|${song.artist}`}>
              <button
                type="button"
                onClick={() => onChange(song)}
                className="block min-h-11 w-full cursor-pointer rounded-2xl px-3 py-2 text-left transition-colors duration-200 hover:text-accent"
              >
                <span className="block break-words">{song.title}</span>
                <span className="block text-small text-muted">{song.artist}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
