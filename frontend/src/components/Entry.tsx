import { useMutation } from "@tanstack/react-query";
import { useState, type DragEvent } from "react";

import { api, ApiError } from "../api/client";
import type { Job, Song } from "../api/types";
import { MAX_RECORDING_S, useRecorder } from "../hooks/useRecorder";
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

type Pending = { audio: Blob; name: string; guess: string };

export function Entry({ onStarted }: { onStarted: (job: Job) => void }) {
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
    setSong(null);
    upload.reset();
    setPending(next);
  }

  const recorder = useRecorder((audio) => choose({ audio, name: "gravacao.webm", guess: "" }));

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

  if (pending) {
    return (
      <section className="mx-auto max-w-xl pt-12">
        <h2 className="text-title font-semibold">Pronto para analisar</h2>
        <div className="mt-6 space-y-6 bg-surface p-6">
          <div>
            <Label>Áudio</Label>
            <p className="mt-1 break-words">{pending.name}</p>
          </div>
          <SongField key={pending.name} initialQuery={pending.guess} value={song} onChange={setSong} />
          <div className="flex flex-wrap gap-2">
            <Button variant="primary" onClick={() => upload.mutate(pending)} disabled={upload.isPending}>
              {upload.isPending ? "Enviando…" : "Analisar"}
            </Button>
            <Button onClick={() => setPending(null)} disabled={upload.isPending}>
              Escolher outro áudio
            </Button>
          </div>
        </div>
        {notice}
      </section>
    );
  }

  const busy = recorder.recording;

  return (
    <section className="mx-auto max-w-xl pt-12">
      <h2 className="text-title font-semibold">Qual som você quer usar como ponto de partida?</h2>
      <p className="mt-2 text-muted">
        Analisamos tom, andamento, estilo e voz, e sugerimos faixas parecidas, uma por vez.
      </p>

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

      <div className="mt-4 flex items-center gap-4">
        {recorder.recording ? (
          <>
            <Button variant="primary" onClick={recorder.stop} disabled={!recorder.canStop}>
              Parar gravação
            </Button>
            <span className="font-mono text-small tabular-nums" role="timer">
              <Label>Gravando</Label> {Math.floor(recorder.elapsed)} / {MAX_RECORDING_S} s
            </span>
          </>
        ) : (
          <>
            <Button onClick={recorder.start}>Gravar pelo microfone</Button>
            <span className="text-small text-muted">Grava até {MAX_RECORDING_S} s</span>
          </>
        )}
      </div>

      {notice}
    </section>
  );
}
