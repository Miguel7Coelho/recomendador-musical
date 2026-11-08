import { useQuery } from "@tanstack/react-query";
import { useRef, useState, type CSSProperties } from "react";

import { api, gatewayUrl } from "../api/client";
import type { Rec } from "../lib/recs";
import { recTitle } from "../lib/recs";
import { RoundButton } from "./ui";

const formatTime = (seconds: number) => {
  if (!Number.isFinite(seconds)) return "–:––";
  const s = Math.floor(seconds);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
};

function PlayIcon({ playing }: { playing: boolean }) {
  return (
    <svg viewBox="0 0 16 16" className="size-4 fill-current" aria-hidden>
      {playing ? <path d="M3 2h4v12H3zM9 2h4v12H9z" /> : <path d="M4 2l10 6-10 6z" />}
    </svg>
  );
}

function fill(value: number, max: number): CSSProperties {
  return { "--fill": `${max > 0 ? (value / max) * 100 : 0}%` } as CSSProperties;
}

type AudioPlayerProps = { src: string; title: string; autoplay: boolean; onEnded: () => void };

function AudioPlayer({ src, title, autoplay, onEnded }: AudioPlayerProps) {
  const audio = useRef<HTMLAudioElement>(null);
  const [playing, setPlaying] = useState(false);
  const [current, setCurrent] = useState(0);
  const [duration, setDuration] = useState(Number.NaN);
  const [volume, setVolume] = useState(1);
  const [failed, setFailed] = useState(false);

  if (failed) return <p className="text-small text-danger">Não foi possível tocar este trecho.</p>;

  const max = Number.isFinite(duration) ? duration : 0;
  return (
    <div className="flex items-center gap-4">
      <audio
        ref={audio}
        src={src}
        preload="auto"
        autoPlay={autoplay}
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        onTimeUpdate={(e) => setCurrent(e.currentTarget.currentTime)}
        onLoadedMetadata={(e) => setDuration(e.currentTarget.duration)}
        onEnded={onEnded}
        onError={() => setFailed(true)}
      />
      <RoundButton
        label={`${playing ? "Pausar" : "Tocar"} ${title}`}
        aria-pressed={playing}
        halo={!playing}
        className="!text-accent"
        onClick={() => (playing ? audio.current?.pause() : void audio.current?.play())}
      >
        <PlayIcon playing={playing} />
      </RoundButton>
      <span className="text-small text-muted tabular-nums">{formatTime(current)}</span>
      <input
        type="range"
        aria-label="Posição na faixa"
        className="range min-w-0 flex-1"
        min={0}
        max={max}
        step={0.1}
        value={Math.min(current, max)}
        style={fill(current, max)}
        onChange={(e) => {
          const time = Number(e.target.value);
          setCurrent(time);
          if (audio.current) audio.current.currentTime = time;
        }}
      />
      <span className="text-small text-muted tabular-nums">{formatTime(duration)}</span>
      <input
        type="range"
        aria-label="Volume"
        className="range hidden w-20 sm:block"
        min={0}
        max={1}
        step={0.05}
        value={volume}
        style={fill(volume, 1)}
        onChange={(e) => {
          const level = Number(e.target.value);
          setVolume(level);
          if (audio.current) audio.current.volume = level;
        }}
      />
    </div>
  );
}

function YouTubePlayer({ title, artist }: { title: string; artist: string }) {
  const video = useQuery({
    queryKey: ["youtube", title, artist],
    queryFn: () => api.youtubeVideo({ title, artist }),
    retry: false,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  });
  if (video.isPending) return <p className="well p-5 text-small text-muted">Procurando o vídeo…</p>;
  if (video.data?.video_id) {
    return (
      <iframe
        title={`Ouvir ${title} no YouTube`}
        src={`https://www.youtube-nocookie.com/embed/${video.data.video_id}`}
        className="block aspect-video w-full rounded-2xl border-0"
        allow="autoplay; encrypted-media; fullscreen; picture-in-picture"
      />
    );
  }
  const search = new URLSearchParams({ search_query: `${artist} ${title}` });
  return (
    <p className="well p-5 text-small text-muted">
      Vídeo indisponível aqui.{" "}
      <a className="text-accent underline" href={`https://www.youtube.com/results?${search}`} target="_blank" rel="noreferrer">
        Procurar no YouTube
      </a>
    </p>
  );
}

type PlayerProps = { rec: Rec; autoplay: boolean; onEnded: () => void };

export function Player({ rec, autoplay, onEnded }: PlayerProps) {
  if (rec.kind === "backup") {
    return <YouTubePlayer key={rec.key} title={rec.track.title} artist={rec.track.artists[0] ?? ""} />;
  }
  if (rec.kind === "spotify") {
    return (
      <div className="overflow-hidden rounded-2xl">
        <iframe
          key={rec.key}
          title={`Ouvir ${recTitle(rec)} no Spotify`}
          src={`https://open.spotify.com/embed/track/${rec.track.spotify_id}?theme=0`}
          height={152}
          className="block w-full border-0"
          allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture"
          loading="lazy"
        />
      </div>
    );
  }
  return (
    <div className="well p-5">
      {rec.track.audio_url ? (
        <AudioPlayer
          key={rec.key}
          src={gatewayUrl(rec.track.audio_url)}
          title={recTitle(rec)}
          autoplay={autoplay}
          onEnded={onEnded}
        />
      ) : (
        <p className="text-small text-muted">Esta faixa não tem trecho para tocar.</p>
      )}
      {rec.track.credit && <p className="mt-2 text-small text-muted">{rec.track.credit}</p>}
    </div>
  );
}
