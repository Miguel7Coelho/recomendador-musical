import { gatewayUrl } from "../api/client";
import type { Rec } from "../lib/recs";
import { recTitle } from "../lib/recs";

type PlayerProps = { rec: Rec; autoplay: boolean; onEnded: () => void };

export function Player({ rec, autoplay, onEnded }: PlayerProps) {
  if (rec.kind === "spotify") {
    return (
      <iframe
        key={rec.key}
        title={`Ouvir ${recTitle(rec)} no Spotify`}
        src={`https://open.spotify.com/embed/track/${rec.track.spotify_id}`}
        height={152}
        className="w-full border-0"
        allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture"
        loading="lazy"
      />
    );
  }
  return (
    <div>
      {rec.track.audio_url ? (
        <audio
          key={rec.key}
          className="w-full"
          controls
          preload="none"
          autoPlay={autoplay}
          src={gatewayUrl(rec.track.audio_url)}
          onEnded={onEnded}
        >
          Seu navegador não toca este áudio.
        </audio>
      ) : (
        <p className="text-small text-muted">Esta faixa não tem trecho para tocar.</p>
      )}
      {rec.track.credit && <p className="mt-2 text-small text-muted">{rec.track.credit}</p>}
    </div>
  );
}
