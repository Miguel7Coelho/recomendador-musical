import type { Features } from "../api/types";
import { formatBpm, formatKey, formatPercent, sortedStyles, styleName } from "../lib/format";
import { Chip, Label, Readout } from "./ui";

function voiceLabel(f: Features): { text: string; value?: string } {
  if (f.vocal_presence < 0.5) return { text: "Instrumental" };
  if (!f.vocal_gender) return { text: "Com voz", value: formatPercent(f.vocal_presence) };
  const confidence = f.vocal_confidence ?? undefined;
  return {
    text: f.vocal_gender === "female" ? "Voz feminina" : "Voz masculina",
    value: confidence === undefined ? undefined : formatPercent(confidence),
  };
}

export function SourceTrack({ features: f }: { features: Features }) {
  const voice = voiceLabel(f);
  return (
    <aside className="panel flip-in self-start p-6">
      <Label>Sua faixa</Label>
      <div className="mt-4 grid grid-cols-2 gap-6 lg:grid-cols-1">
        <Readout label="Tom" value={f.camelot} detail={formatKey(f.key, f.scale)} confidence={f.key_strength} />
        <Readout label="BPM" value={formatBpm(f.bpm)} confidence={f.bpm_confidence} />
      </div>
      <div className="mt-6">
        <Label>Gênero</Label>
        <p className="mt-1 font-medium">{f.genre_top}</p>
        <div className="mt-2 flex flex-wrap gap-2">
          {sortedStyles(f.styles).map(([style, probability]) => (
            <Chip key={style} value={formatPercent(probability)}>
              {styleName(style)}
            </Chip>
          ))}
        </div>
      </div>
      <div className="mt-6">
        <Label>Voz</Label>
        <div className="mt-2">
          <Chip value={voice.value}>{voice.text}</Chip>
        </div>
      </div>
    </aside>
  );
}
