import { useCallback, useEffect, useRef, useState } from "react";

// O corte do servidor exige 3 s; a folga cobre o tempo até o microfone abrir.
export const MIN_RECORDING_S = 4;
export const MAX_RECORDING_S = 10;
const HEARD_LEVEL = 0.02;
const SILENCE_WARNING_S = 2;

function rms(analyser: AnalyserNode, samples: Uint8Array<ArrayBuffer>): number {
  analyser.getByteTimeDomainData(samples);
  const sum = samples.reduce((total, sample) => total + ((sample - 128) / 128) ** 2, 0);
  return Math.sqrt(sum / samples.length);
}

export function useRecorder(onDone: (audio: Blob) => void) {
  const [recording, setRecording] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [level, setLevel] = useState(0);
  const [heard, setHeard] = useState(false);
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

  const cancel = useCallback(() => {
    discard.current = true;
    stop();
  }, [stop]);

  const start = useCallback(async () => {
    setError(null);
    discard.current = false;
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        // Os filtros de chamada de voz tratam música como ruído e a apagam.
        audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false },
      });
    } catch {
      setError("Não foi possível acessar o microfone. Verifique a permissão do navegador.");
      return;
    }
    const rec = new MediaRecorder(stream);
    const chunks: Blob[] = [];
    const context = new AudioContext();
    const analyser = context.createAnalyser();
    context.createMediaStreamSource(stream).connect(analyser);
    const samples = new Uint8Array(analyser.fftSize);
    rec.ondataavailable = (e) => chunks.push(e.data);
    rec.onstop = () => {
      stream.getTracks().forEach((t) => t.stop());
      void context.close();
      setRecording(false);
      if (!discard.current) done.current(new Blob(chunks, { type: rec.mimeType }));
    };
    recorder.current = rec;
    rec.start();
    setRecording(true);
    setElapsed(0);
    setLevel(0);
    setHeard(false);
    const startedAt = performance.now();
    timer.current = window.setInterval(() => {
      const seconds = (performance.now() - startedAt) / 1000;
      setElapsed(Math.min(seconds, MAX_RECORDING_S));
      const current = rms(analyser, samples);
      setLevel(current);
      if (current > HEARD_LEVEL) setHeard(true);
      if (seconds >= MAX_RECORDING_S) stop();
    }, 100);
  }, [stop]);

  useEffect(
    () => () => {
      discard.current = true;
      stop();
    },
    [stop],
  );

  return {
    recording,
    elapsed,
    level,
    silent: !heard && elapsed >= SILENCE_WARNING_S,
    error,
    start,
    stop,
    cancel,
    canStop: elapsed >= MIN_RECORDING_S,
  };
}
