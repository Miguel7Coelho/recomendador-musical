import { useMutation } from "@tanstack/react-query";
import { useState, type DragEvent } from "react";

import { api, ApiError } from "../api/client";
import type { Job } from "../api/types";
import { MAX_RECORDING_S, useRecorder } from "../hooks/useRecorder";
import { Button, Label, Notice } from "./ui";

const MAX_BYTES = 25 * 1024 * 1024;
const TOO_BIG = "O arquivo passa de 25 MB. Envie um trecho menor.";

function uploadError(error: unknown): string {
  if (error instanceof ApiError) return error.status === 413 ? TOO_BIG : error.message;
  return "Não foi possível falar com o servidor. Tente de novo.";
}

export function Entry({ onStarted }: { onStarted: (job: Job) => void }) {
  const [localError, setLocalError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const upload = useMutation({
    mutationFn: ({ audio, name }: { audio: Blob; name: string }) => api.analyze(audio, name),
    onSuccess: onStarted,
  });
  const recorder = useRecorder((audio) => upload.mutate({ audio, name: "gravacao.webm" }));

  function send(file: File | undefined) {
    if (!file) return;
    if (file.size > MAX_BYTES) {
      setLocalError(TOO_BIG);
      return;
    }
    setLocalError(null);
    upload.mutate({ audio: file, name: file.name });
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setDragging(false);
    send(e.dataTransfer.files[0]);
  }

  const error = localError ?? recorder.error ?? (upload.isError ? uploadError(upload.error) : null);
  const busy = upload.isPending || recorder.recording;

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
            send(e.target.files?.[0]);
            e.target.value = "";
          }}
        />
        <span className="font-medium">{upload.isPending ? "Enviando…" : "Escolha um arquivo de áudio"}</span>
        <span className="mt-1 block text-small text-muted">ou arraste para cá · até 25 MB · mínimo de 3 s</span>
      </label>

      <div className="mt-4 flex items-center gap-4">
        {recorder.recording ? (
          <>
            <Button variant="primary" onClick={recorder.stop} disabled={!recorder.canStop}>
              Parar e analisar
            </Button>
            <span className="font-mono text-small tabular-nums" role="timer">
              <Label>Gravando</Label> {Math.floor(recorder.elapsed)} / {MAX_RECORDING_S} s
            </span>
          </>
        ) : (
          <>
            <Button onClick={recorder.start} disabled={upload.isPending}>
              Gravar pelo microfone
            </Button>
            <span className="text-small text-muted">Grava até {MAX_RECORDING_S} s</span>
          </>
        )}
      </div>

      {error && (
        <div className="mt-6">
          <Notice tone="danger">{error}</Notice>
        </div>
      )}
    </section>
  );
}
