import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";

import { api } from "../api/client";
import type { JobResult, Song, SongProfile } from "../api/types";
import { formatBpm } from "../lib/format";
import { Failed } from "./Progress";
import { Results } from "./Results";
import { Chip, Label, Readout } from "./ui";

function SongSource({ song }: { song: SongProfile }) {
  return (
    <aside className="border-line lg:border-r lg:pr-8">
      <Label>Sua música</Label>
      <p className="mt-4 text-title font-semibold break-words">{song.title}</p>
      <p className="text-muted">{song.artist}</p>
      <div className="mt-6 grid grid-cols-2 gap-6 lg:grid-cols-1">
        <Readout label="Tom" value={song.camelot ?? "–"} />
        <Readout label="BPM" value={song.bpm ? formatBpm(song.bpm) : "–"} />
      </div>
      {song.tags.length > 0 && (
        <div className="mt-6">
          <Label>Etiquetas</Label>
          <div className="mt-2 flex flex-wrap gap-2">
            {song.tags.map((tag) => (
              <Chip key={tag}>{tag}</Chip>
            ))}
          </div>
        </div>
      )}
    </aside>
  );
}

export function SongResults({ song, onReset }: { song: Song; onReset: () => void }) {
  const search = useQuery({
    queryKey: ["song-recommendation", song.title, song.artist],
    queryFn: () => api.recommendSong(song),
    retry: false,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  });
  const results = search.data?.results;
  const result = useMemo<JobResult>(() => ({ catalog: [], relaxed: [], spotify: results ?? [] }), [results]);

  if (search.isPending) {
    return (
      <section className="mx-auto max-w-xl pt-12">
        <h2 className="text-title font-semibold">Procurando faixas parecidas</h2>
        <p className="mt-2 text-muted">
          {song.title} · {song.artist}
        </p>
      </section>
    );
  }
  if (search.isError) {
    return <Failed message={search.error.message} onRetry={onReset} retryLabel="Fazer outra busca" />;
  }
  return <Results features={{}} source={<SongSource song={search.data.song} />} result={result} />;
}
