import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState, type ReactNode } from "react";

import { api } from "../api/client";
import type { CatalogRecommendation, Features, Filters, JobResult } from "../api/types";
import { formatBpm, formatScore, sortedStyles, styleName } from "../lib/format";
import { fromCatalog, fromExternal, recArtist, recTitle, spotifyFirst, type Rec } from "../lib/recs";
import { useSession } from "../store";
import { Drawer } from "./Drawer";
import { DEFAULT_FILTERS, FilterForm } from "./FilterForm";
import { Player } from "./Player";
import { Button, Chip, Label, Notice, Readout } from "./ui";

type Similar = { seed: string; items: Rec[] };

type Seed = Partial<Pick<Features, "styles" | "genre_top">>;

async function moreLike(rec: Rec, features: Seed): Promise<Similar> {
  const seed = recTitle(rec);
  if (rec.kind === "catalog") {
    const out = await api.moreLikeTrack(rec.track.id);
    return { seed, items: out.results.map(fromCatalog) };
  }
  if (rec.kind === "backup") {
    const out = await api.recommendSong({ title: rec.track.title, artist: rec.track.artists[0] ?? "" });
    return { seed, items: out.results.map(fromExternal) };
  }
  const { camelot, bpm, spotify_id, title, artists } = rec.track;
  const track = artists[0] ? { title, artist: artists[0] } : undefined;
  const { styles, genre_top } = features;
  const out = await api.moreLikeSpotify(spotify_id, { camelot, bpm, styles, genre_top, track });
  return { seed, items: out.results.map(fromExternal) };
}

const MAX_CARD_TAGS = 6;

function RecTags({ rec }: { rec: Rec }) {
  const song = rec.kind === "catalog" ? null : { title: rec.track.title, artist: rec.track.artists[0] ?? "" };
  // Só a faixa na tela pede etiquetas; as do catálogo já vieram da análise do áudio.
  const lastfm = useQuery({
    queryKey: ["song-tags", song?.title, song?.artist],
    queryFn: () => api.songTags(song!),
    enabled: song !== null,
    retry: false,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  });
  const tags =
    rec.kind === "catalog"
      ? sortedStyles(rec.track.styles).slice(0, MAX_CARD_TAGS).map(([style]) => styleName(style))
      : (lastfm.data?.tags ?? []);
  if (tags.length === 0) return null;
  return (
    <div>
      <Label>Etiquetas</Label>
      <div className="mt-2 flex flex-wrap gap-2">
        {tags.map((tag) => (
          <Chip key={tag}>{tag}</Chip>
        ))}
      </div>
    </div>
  );
}

type ResultsProps = {
  /** Sem job (música pesquisada) não há análise para refiltrar nem catálogo. */
  jobId?: string;
  features: Seed;
  source: ReactNode;
  result: JobResult;
};

export function Results({ jobId, features, source, result }: ResultsProps) {
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);
  const [filtered, setFiltered] = useState<CatalogRecommendation | null>(null);
  const [showFilters, setShowFilters] = useState(false);
  const [similar, setSimilar] = useState<Similar | null>(null);
  const [index, setIndex] = useState(0);
  const { favorites, autoplay, toggleFavorite, toggleAutoplay } = useSession();

  const catalog = filtered?.results ?? result.catalog;
  const original = useMemo(() => spotifyFirst(catalog, result.spotify), [catalog, result.spotify]);

  const more = useMutation({
    mutationFn: (rec: Rec) => moreLike(rec, features),
    onSuccess: (out) => {
      if (out.items.length === 0) return;
      setSimilar(out);
      setIndex(0);
    },
  });

  const refilter = useMutation({
    mutationFn: (next: Filters) => api.refilter(jobId ?? "", { filters: next }),
    onSuccess: (out, next) => {
      setFilters(next);
      setFiltered(out);
      setSimilar(null);
      // Os filtros só mudam o catálogo: vai direto para o que mudou.
      setIndex(out.results.length > 0 ? result.spotify.length : 0);
      setShowFilters(false);
    },
  });

  const items = similar?.items ?? original;
  const rec = items[index];
  const favorite = rec ? rec.key in favorites : false;
  const noMatches = more.isSuccess && more.data.items.length === 0;
  const filtersActive = JSON.stringify(filters) !== JSON.stringify(DEFAULT_FILTERS);

  const next = () => setIndex((i) => (i + 1) % items.length);
  const previous = () => setIndex((i) => (i - 1 + items.length) % items.length);
  const shuffle = () =>
    setIndex((i) => (i + 1 + Math.floor(Math.random() * (items.length - 1))) % items.length);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.ctrlKey || e.metaKey || e.altKey || !rec || document.querySelector("dialog[open]")) return;
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement) return;
      if (e.key === "n") next();
      else if (e.key === "p") previous();
      else if (e.key === "a" && items.length > 1) shuffle();
      else if (e.key === "f") toggleFavorite(rec);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  return (
    <div className="grid gap-8 lg:grid-cols-[280px_1fr]">
      {source}

      <section className="min-w-0 space-y-6" aria-label="Recomendações">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <Label>
            {similar ? `Parecidas com ${similar.seed}` : "Recomendação"} · {rec ? index + 1 : 0} de {items.length}
          </Label>
          <div className="flex flex-wrap gap-2">
            {similar && (
              <Button
                onClick={() => {
                  setSimilar(null);
                  setIndex(0);
                }}
              >
                Voltar aos resultados
              </Button>
            )}
            {jobId && (
              <Button onClick={() => setShowFilters(true)}>{filtersActive ? "Filtros ativos" : "Filtros"}</Button>
            )}
          </div>
        </div>

        {!similar && filtered?.results.length === 0 && (
          <Notice>Nenhuma faixa do catálogo passou nesses filtros. Mostrando só o Spotify.</Notice>
        )}
        {!similar && jobId && !result.spotify_error && result.spotify.length === 0 && (
          <Notice>O Spotify não teve sugestões para este estilo. Mostrando só o catálogo.</Notice>
        )}
        {more.isError && <Notice tone="danger">{more.error.message}</Notice>}
        {noMatches && <Notice>Não encontramos faixas parecidas com esta.</Notice>}

        {rec ? (
          <article className="space-y-6 bg-surface p-6">
            <header>
              <Label>{{ catalog: "Catálogo FMA", spotify: "Spotify", backup: "YouTube" }[rec.kind]}</Label>
              <h2 className="mt-2 text-headline font-semibold break-words">{recTitle(rec)}</h2>
              <p className="mt-1 text-body">{recArtist(rec)}</p>
            </header>

            <div className="grid grid-cols-2 gap-6 sm:grid-cols-3">
              <Readout label="Tom" value={rec.kind === "backup" ? "–" : rec.track.camelot} />
              <Readout label="BPM" value={rec.kind === "backup" ? "–" : formatBpm(rec.track.bpm)} />
              {rec.kind === "catalog" && <Readout label="Afinidade" value={formatScore(rec.track.score)} />}
            </div>

            <RecTags rec={rec} />

            <p className="text-small">
              <span className="text-muted">Parecida porque: </span>
              {rec.track.explanation}
            </p>

            <Player rec={rec} autoplay={autoplay} onEnded={() => autoplay && next()} />

            <div className="flex flex-wrap gap-2">
              <Button variant="primary" onClick={next} disabled={items.length < 2} aria-keyshortcuts="n">
                Próxima
              </Button>
              <Button onClick={previous} disabled={items.length < 2} aria-keyshortcuts="p">
                Anterior
              </Button>
              <Button onClick={shuffle} disabled={items.length < 2} aria-keyshortcuts="a">
                Aleatória
              </Button>
              <Button aria-pressed={favorite} onClick={() => toggleFavorite(rec)} aria-keyshortcuts="f">
                {favorite ? "Favoritada" : "Favoritar"}
              </Button>
              <Button onClick={() => more.mutate(rec)} disabled={more.isPending}>
                {more.isPending ? "Buscando…" : "Mais parecidas com esta"}
              </Button>
              <Button aria-pressed={autoplay} onClick={toggleAutoplay}>
                Avanço automático
              </Button>
            </div>
            <p className="font-mono text-label text-muted">Atalhos: N próxima · P anterior · A aleatória · F favoritar</p>
          </article>
        ) : (
          <Notice>Nenhuma recomendação encontrada para esta faixa.</Notice>
        )}
      </section>

      {jobId && (
        <Drawer open={showFilters} onClose={() => setShowFilters(false)} title="Filtros">
          <FilterForm
            value={filters}
            pending={refilter.isPending}
            error={refilter.isError ? refilter.error.message : null}
            onApply={(next) => refilter.mutate(next)}
          />
        </Drawer>
      )}
    </div>
  );
}
