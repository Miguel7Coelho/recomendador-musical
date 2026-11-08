import { useCallback, useEffect, useRef, useState } from "react";

export const MIN_RECORDING_S = 3;
export const MAX_RECORDING_S = 10;

export function useRecorder(onDone: (audio: Blob) => void) {
  const [recording, setRecording] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const recorder = useRef<MediaRecorder | null>(null);
  const timer = useRef<number | undefined>(undefined);
  const discard = useRef(false);
  const done = useRef(onDone);
  done.current = onDone;

  const stop = useCallback(() => {
    window.clearInterval(timer.current);
    if (recorder.current?.state === "recording") recorder.current.stop();
  }, []);

  const start = useCallback(async () => {
    setError(null);
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      setError("Não foi possível acessar o microfone. Verifique a permissão do navegador.");
      return;
    }
    const rec = new MediaRecorder(stream);
    const chunks: Blob[] = [];
    rec.ondataavailable = (e) => chunks.push(e.data);
    rec.onstop = () => {
      stream.getTracks().forEach((t) => t.stop());
      setRecording(false);
      if (!discard.current) done.current(new Blob(chunks, { type: rec.mimeType }));
    };
    recorder.current = rec;
    rec.start();
    setRecording(true);
    setElapsed(0);
    const startedAt = performance.now();
    timer.current = window.setInterval(() => {
      const seconds = (performance.now() - startedAt) / 1000;
      setElapsed(Math.min(seconds, MAX_RECORDING_S));
      if (seconds >= MAX_RECORDING_S) stop();
    }, 200);
  }, [stop]);

  useEffect(
    () => () => {
      discard.current = true;
      stop();
    },
    [stop],
  );

  return { recording, elapsed, error, start, stop, canStop: elapsed >= MIN_RECORDING_S };
}
