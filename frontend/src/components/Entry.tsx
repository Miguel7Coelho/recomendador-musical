import { useMutation } from "@tanstack/react-query";
import { useState, type DragEvent } from "react";

import { api, ApiError } from "../api/client";
import type { Job, Song } from "../api/types";
import { MAX_RECORDING_S, MIN_RECORDING_S, useRecorder } from "../hooks/useRecorder";
import { SongField } from "./SongField";
import { Button, Label, Notice } from "./ui";

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
    <div className="mt-8 space-y-5 border border-danger bg-surface p-6">
      <div className="flex items-center justify-between gap-4">
        <p className="flex items-center gap-3 font-medium">
          <span className="size-3 rounded-full bg-danger motion-safe:animate-pulse" aria-hidden />
          Gravando
        </p>
        <span className="font-mono text-small tabular-nums" role="timer">
          {Math.floor(elapsed)} / {MAX_RECORDING_S} s
        </span>
      </div>
      <div>
        <Label>Tempo</Label>
        <div className="mt-2 h-1 bg-raised">
          <div className="h-full bg-accent" style={{ width: `${(elapsed / MAX_RECORDING_S) * 100}%` }} />
        </div>
      </div>
      <div>
        <Label>Som captado</Label>
        <div className="mt-2 h-3 bg-raised">
          <div className="h-full bg-danger transition-[width] duration-100" style={{ width: `${Math.min(level * 400, 100)}%` }} />
        </div>
      </div>
      {silent && <p className="text-small text-danger">Não estamos captando som. Confira o microfone.</p>}
      <div className="flex flex-wrap items-center gap-3">
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

  const busy = recorder.recording;

  return (
    <section className="mx-auto max-w-xl pt-12">
      <h2 className="text-title font-semibold">Qual som você quer usar como ponto de partida?</h2>
      <p className="mt-2 text-muted">
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
      ) : pending ? (
        <div className="mt-8 flex items-center justify-between gap-4 bg-surface p-6">
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
            className={`mt-8 block border border-dashed bg-surface p-8 text-center transition-colors duration-100 has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-accent ${
              busy ? "border-line" : "cursor-pointer border-control hover:bg-raised"
            } ${dragging ? "border-accent" : ""}`}
          >
            <input
              type="file"
              accept="audio/*"
              className="sr-only"
              disabled={busy}
              onChange={(e) => {
                pick(e.target.files?.[0]);
                e.target.value = "";
              }}
            />
            <span className="font-medium">Escolha um arquivo de áudio</span>
            <span className="mt-1 block text-small text-muted">ou arraste para cá · até 25 MB · mínimo de 3 s</span>
          </label>
      )}

      <div className="mt-4 flex items-center gap-4">
        {!recorder.recording && (
          <>
            <Button onClick={recorder.start} disabled={upload.isPending}>
              Gravar pelo microfone
            </Button>
            <span className="text-small text-muted">Grava até {MAX_RECORDING_S} s</span>
          </>
        )}
      </div>

      <div className="mt-6">
        <SongField key={pending?.guess ?? ""} initialQuery={pending?.guess ?? ""} value={song} onChange={setSong} onSearch={pending ? undefined : onSearch} />
      </div>

      {pending && (
        <Button variant="primary" className="mt-6" onClick={() => upload.mutate(pending)} disabled={upload.isPending}>
          {upload.isPending ? "Enviando…" : "Analisar"}
        </Button>
      )}

      {notice}
    </section>
  );
}
