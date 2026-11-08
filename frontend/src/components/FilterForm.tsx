import { useState, type ReactNode } from "react";

import type { Filters } from "../api/types";
import { Button, Label, Notice } from "./ui";

export const DEFAULT_FILTERS: Filters = { key: "exact", genre: "style", voice: "on", locked: [] };

type Lockable = "key" | "genre" | "voice";

const inputClass = "field tabular-nums";

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block">
      <Label>{label}</Label>
      {children}
    </label>
  );
}

function Lock({ checked, onChange }: { checked: boolean; onChange: () => void }) {
  return (
    <label className="mt-1 flex min-h-11 items-center gap-2 text-small text-muted">
      <input type="checkbox" className="size-4 accent-accent" checked={checked} onChange={onChange} />
      Travar (nunca ampliar a busca)
    </label>
  );
}

function RangeField({ label, min, max, onMin, onMax }: {
  label: string;
  min?: number;
  max?: number;
  onMin: (v?: number) => void;
  onMax: (v?: number) => void;
}) {
  const parse = (value: string) => (value === "" ? undefined : Number(value));
  return (
    <fieldset>
      <legend>
        <Label>{label}</Label>
      </legend>
      <div className="grid grid-cols-2 gap-3">
        <input aria-label={`${label}: mínimo`} placeholder="mín." type="number" min={0} className={inputClass}
          value={min ?? ""} onChange={(e) => onMin(parse(e.target.value))} />
        <input aria-label={`${label}: máximo`} placeholder="máx." type="number" min={0} className={inputClass}
          value={max ?? ""} onChange={(e) => onMax(parse(e.target.value))} />
      </div>
    </fieldset>
  );
}

type FilterFormProps = {
  value: Filters;
  pending: boolean;
  error: string | null;
  onApply: (filters: Filters) => void;
};

export function FilterForm({ value, pending, error, onApply }: FilterFormProps) {
  const [draft, setDraft] = useState<Filters>(value);
  const patch = (changes: Partial<Filters>) => setDraft((d) => ({ ...d, ...changes }));
  const isLocked = (name: Lockable) => draft.locked?.includes(name) ?? false;
  const toggleLock = (name: Lockable) =>
    patch({ locked: isLocked(name) ? draft.locked?.filter((l) => l !== name) : [...(draft.locked ?? []), name] });

  const inverted = (min?: number, max?: number) => min !== undefined && max !== undefined && min > max;
  const invalid = inverted(draft.bpm_min, draft.bpm_max) || inverted(draft.year_min, draft.year_max);

  return (
    <form
      className="space-y-5"
      onSubmit={(e) => {
        e.preventDefault();
        if (!invalid) onApply(draft);
      }}
    >
      <p className="text-small text-muted">
        Valem para o catálogo. As sugestões do Spotify já vêm filtradas por gênero e BPM e continuam iguais.
      </p>

      <div>
        <Field label="Tom">
          <select className={inputClass} value={draft.key} onChange={(e) => patch({ key: e.target.value as Filters["key"] })}>
            <option value="exact">Exato</option>
            <option value="compatible">Compatível</option>
            <option value="off">Desligado</option>
          </select>
        </Field>
        <Lock checked={isLocked("key")} onChange={() => toggleLock("key")} />
      </div>

      <div>
        <Field label="Gênero">
          <select className={inputClass} value={draft.genre} onChange={(e) => patch({ genre: e.target.value as Filters["genre"] })}>
            <option value="style">Mesmo estilo</option>
            <option value="genre">Mesmo gênero amplo</option>
            <option value="off">Desligado</option>
          </select>
        </Field>
        <Lock checked={isLocked("genre")} onChange={() => toggleLock("genre")} />
      </div>

      <div>
        <Field label="Voz">
          <select className={inputClass} value={draft.voice} onChange={(e) => patch({ voice: e.target.value as Filters["voice"] })}>
            <option value="on">Igual à da sua faixa</option>
            <option value="off">Desligado</option>
          </select>
        </Field>
        <Lock checked={isLocked("voice")} onChange={() => toggleLock("voice")} />
      </div>

      <div>
        <RangeField label="BPM" min={draft.bpm_min} max={draft.bpm_max}
          onMin={(bpm_min) => patch({ bpm_min })} onMax={(bpm_max) => patch({ bpm_max })} />
        <p className="mt-1 text-small text-muted">Dobro e metade do andamento também contam.</p>
      </div>

      <RangeField label="Ano" min={draft.year_min} max={draft.year_max}
        onMin={(year_min) => patch({ year_min })} onMax={(year_max) => patch({ year_max })} />

      {invalid && <Notice tone="danger">O mínimo não pode ser maior que o máximo.</Notice>}
      {error && <Notice tone="danger">{error}</Notice>}

      <div className="flex flex-wrap gap-2">
        <Button type="submit" variant="primary" disabled={pending || invalid}>
          {pending ? "Aplicando…" : "Aplicar filtros"}
        </Button>
        <Button onClick={() => setDraft(DEFAULT_FILTERS)}>Restaurar padrões</Button>
      </div>
    </form>
  );
}
