import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { api } from "../api/client";
import type { Song } from "../api/types";
import { Button, Label } from "./ui";

const DEBOUNCE_MS = 300;

type SongFieldProps = { initialQuery: string; value: Song | null; onChange: (song: Song | null) => void };

export function SongField({ initialQuery, value, onChange }: SongFieldProps) {
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
        <div className="mt-1 flex items-center justify-between gap-4 rounded-sm bg-raised px-3 py-2">
          <div className="min-w-0">
            <p className="font-medium break-words">{value.title}</p>
            <p className="text-small text-muted">{value.artist}</p>
          </div>
          <Button onClick={() => onChange(null)}>Trocar</Button>
        </div>
      </div>
    );
  }

  const results = songs.data?.results ?? [];
  return (
    <div>
      <label className="block">
        <Label>Ou pesquise a música aqui (opcional)</Label>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Artista e nome da música"
          autoComplete="off"
          className="mt-1 min-h-11 w-full rounded-sm border border-control bg-raised px-3"
        />
      </label>
      <p className="mt-1 text-small text-muted">
        Com o áudio dela, usamos o que os ouvintes também escutam. Em beats próprios, deixe em branco.
      </p>
      {results.length > 0 && (
        <ul className="mt-2 divide-y divide-line border-y border-line" aria-label="Sugestões">
          {results.map((song) => (
            <li key={`${song.title}|${song.artist}`}>
              <button
                type="button"
                onClick={() => onChange(song)}
                className="block min-h-11 w-full cursor-pointer px-3 py-2 text-left transition-colors duration-100 hover:bg-raised"
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
