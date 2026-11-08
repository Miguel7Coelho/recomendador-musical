import type { JobStatus } from "../api/types";
import { Button, Label, Notice } from "./ui";

const STAGES: Array<{ status: JobStatus; label: string; hint: string }> = [
  { status: "separating", label: "Separando", hint: "voz, bateria, baixo e demais instrumentos" },
  { status: "analyzing", label: "Analisando", hint: "tom, andamento, estilo e voz" },
  { status: "searching", label: "Buscando", hint: "faixas parecidas no catálogo e no Spotify" },
];

export function Progress({ status }: { status: JobStatus }) {
  const current = STAGES.findIndex((s) => s.status === status);
  return (
    <section className="mx-auto max-w-xl pt-12">
      <h2 className="text-title font-semibold">Analisando sua faixa</h2>
      <p className="mt-2 text-muted">Costuma levar uns 20 s, ou mais na primeira análise.</p>
      <ol className="mt-8 divide-y divide-line border-y border-line" aria-live="polite">
        {STAGES.map((stage, i) => {
          const state = i < current ? "feito" : i === current ? "agora" : "a seguir";
          return (
            <li
              key={stage.status}
              aria-current={i === current ? "step" : undefined}
              className="flex items-baseline gap-4 py-3"
            >
              <span className={`font-medium ${i === current ? "text-accent" : i > current ? "text-muted" : ""}`}>
                {stage.label}
              </span>
              <span className="flex-1 text-small text-muted">{stage.hint}</span>
              <Label>{state}</Label>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

type FailedProps = { message: string; onRetry: () => void; retryLabel?: string };

export function Failed({ message, onRetry, retryLabel = "Enviar outra faixa" }: FailedProps) {
  return (
    <section className="mx-auto max-w-xl pt-12">
      <Notice tone="danger">{message}</Notice>
      <Button variant="primary" className="mt-6" onClick={onRetry}>
        {retryLabel}
      </Button>
    </section>
  );
}
