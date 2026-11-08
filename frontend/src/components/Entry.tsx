import { useMutation } from "@tanstack/react-query";
import { useState, type CSSProperties, type DragEvent } from "react";

import { api, ApiError } from "../api/client";
import type { Job, Song } from "../api/types";
import { MAX_RECORDING_S, MIN_RECORDING_S, useRecorder } from "../hooks/useRecorder";
import { SongField } from "./SongField";
import { Button, Icon, Label, Notice, RoundButton } from "./ui";

const MIC_ICON = "M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3zM5 11a7 7 0 0 0 14 0M12 18v3";

const MAX_BYTES = 25 * 1024 * 1024;
const TOO_BIG = "O arquivo passa de 25 MB. Envie um trecho menor.";

function uploadError(error: unknown): string {
  if (error instanceof ApiError) return error.status === 413 ? TOO_BIG : error.message;
  return "Não foi possível falar com o servidor. Tente de novo.";
}

/** "Artista - Música.mp3" → "Artista Música"; nomes em outro formato não dizem nada. */
function guessFromFilename(name: string): string {
  const base = name.replace(/\.[^.]+$/, "").replace(/_/g, " ");
  return base.includes(" - ") ? base.replace(/ - /g, " ").trim() : "";
}

type Pending = { audio: Blob; name: string; guess: string; label?: string };

type RecordingPanelProps = {
  elapsed: number;
  level: number;
  silent: boolean;
  canStop: boolean;
  onStop: () => void;
  onCancel: () => void;
};

function RecordingPanel({ elapsed, level, silent, canStop, onStop, onCancel }: RecordingPanelProps) {
  return (
    <div className="panel flip-in mt-10 space-y-6 p-6 sm:p-8">
      <div className="flex flex-col items-center gap-4 pt-6">
        <span className="round round-lg halo !text-danger" style={{ "--halo-color": "var(--color-danger)" } as CSSProperties}>
          <Icon path={MIC_ICON} size={28} />
        </span>
        <p className="mt-5 text-title font-semibold">Gravando</p>
        <span className="text-small text-muted tabular-nums" role="timer">
          {Math.floor(elapsed)} / {MAX_RECORDING_S} s
        </span>
      </div>
      <div>
        <Label>Tempo</Label>
        <span className="meter mt-2">
          <span style={{ width: `${(elapsed / MAX_RECORDING_S) * 100}%` }} />
        </span>
      </div>
      <div>
        <Label>Som captado</Label>
        <span className="meter mt-2">
          <span className="!bg-danger transition-[width] duration-100" style={{ width: `${Math.min(level * 400, 100)}%` }} />
        </span>
      </div>
      {silent && <p className="text-center text-small text-danger">Não estamos captando som. Confira o microfone.</p>}
      <div className="flex flex-wrap items-center justify-center gap-3">
        <Button variant="primary" onClick={onStop} disabled={!canStop}>
          {canStop ? "Parar e buscar" : `Mínimo de ${MIN_RECORDING_S} s`}
        </Button>
        <Button onClick={onCancel}>Cancelar</Button>
      </div>
    </div>
  );
}

type EntryProps = { onStarted: (job: Job) => void; onSearch: (song: Song) => void };

export function Entry({ onStarted, onSearch }: EntryProps) {
  const [localError, setLocalError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [pending, setPending] = useState<Pending | null>(null);
  const [song, setSong] = useState<Song | null>(null);
  const upload = useMutation({
    mutationFn: ({ audio, name }: Pending) => api.analyze(audio, name, song ?? undefined),
    onSuccess: onStarted,
  });

  function choose(next: Pending) {
    setLocalError(null);
    upload.reset();
    setPending(next);
  }

  const recorder = useRecorder((audio) => {
    const recording = { audio, name: "gravacao.webm", guess: "", label: "Gravação do microfone" };
    choose(recording);
    upload.mutate(recording); // parar a gravação já é o pedido de busca
  });

  function pick(file: File | undefined) {
    if (!file) return;
    if (file.size > MAX_BYTES) {
      setLocalError(TOO_BIG);
      return;
    }
    choose({ audio: file, name: file.name, guess: guessFromFilename(file.name) });
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setDragging(false);
    pick(e.dataTransfer.files[0]);
  }

  const error = localError ?? recorder.error ?? (upload.isError ? uploadError(upload.error) : null);
  const notice = error && (
    <div className="mt-6">
      <Notice tone="danger">{error}</Notice>
    </div>
  );

  const panel = (
    <div className="panel flip-in mt-10 space-y-8 p-6 sm:p-8">
      {pending ? (
        <div className="well flex items-center justify-between gap-4 p-5">
          <div className="min-w-0">
            <Label>Áudio</Label>
            <p className="mt-1 break-words">{pending.label ?? pending.name}</p>
          </div>
          <Button onClick={() => setPending(null)} disabled={upload.isPending}>
            Trocar
          </Button>
        </div>
      ) : (
        <label
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={`well block cursor-pointer p-8 text-center has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-accent ${
            dragging ? "outline-2 outline-accent" : ""
          }`}
        >
          <input
            type="file"
            accept="audio/*"
            className="sr-only"
            onChange={(e) => {
              pick(e.target.files?.[0]);
              e.target.value = "";
            }}
          />
          <span className="font-medium">Escolha um arquivo de áudio</span>
          <span className="mt-1 block text-small text-muted">ou arraste para cá · até 25 MB · mínimo de 3 s</span>
        </label>
      )}

      <div className="flex flex-col items-center gap-3">
        <RoundButton label="Gravar pelo microfone" large halo onClick={recorder.start} disabled={upload.isPending}>
          <Icon path={MIC_ICON} size={28} />
        </RoundButton>
        <p className="mt-5 text-small text-muted">Gravar pelo microfone · até {MAX_RECORDING_S} s</p>
      </div>

      <SongField key={pending?.guess ?? ""} initialQuery={pending?.guess ?? ""} value={song} onChange={setSong} onSearch={pending ? undefined : onSearch} />

      {pending && (
        <div className="text-center">
          <Button variant="primary" onClick={() => upload.mutate(pending)} disabled={upload.isPending}>
            {upload.isPending ? "Enviando…" : "Analisar"}
          </Button>
        </div>
      )}
    </div>
  );

  return (
    <section className="mx-auto max-w-2xl pt-8 sm:pt-14">
      <h2 className="text-center text-hero font-semibold tracking-tight">Qual som você quer usar como ponto de partida?</h2>
      <p className="mx-auto mt-5 max-w-xl text-center text-lead text-muted">
        Analisamos tom, andamento, estilo e voz, e sugerimos faixas parecidas, uma por vez.
      </p>

      {recorder.recording ? (
        <RecordingPanel
          elapsed={recorder.elapsed}
          level={recorder.level}
          silent={recorder.silent}
          canStop={recorder.canStop}
          onStop={recorder.stop}
          onCancel={recorder.cancel}
        />
      ) : (
        panel
      )}

      {notice}
    </section>
  );
}
