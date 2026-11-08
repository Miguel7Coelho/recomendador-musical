import type { ButtonHTMLAttributes, ReactNode } from "react";

import { formatPercent } from "../lib/format";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "ghost" };

export function Button({ variant = "ghost", className = "", ...props }: ButtonProps) {
  const look =
    variant === "primary"
      ? "bg-accent text-on-accent font-medium hover:bg-text"
      : "border border-control text-text hover:bg-raised aria-pressed:border-accent aria-pressed:text-accent";
  return (
    <button
      type="button"
      className={`min-h-11 cursor-pointer rounded-sm px-4 transition-colors duration-100 disabled:cursor-not-allowed disabled:opacity-50 ${look} ${className}`}
      {...props}
    />
  );
}

export function Label({ children }: { children: ReactNode }) {
  return <span className="font-mono text-label tracking-label text-muted uppercase">{children}</span>;
}

type ReadoutProps = { label: string; value: string; detail?: string; confidence?: number };

export function Readout({ label, value, detail, confidence }: ReadoutProps) {
  return (
    <div>
      <Label>{label}</Label>
      <p className="font-mono text-readout font-medium tabular-nums">{value}</p>
      {detail && <p className="font-mono text-small text-muted">{detail}</p>}
      {confidence !== undefined && (
        <div className="mt-2">
          <div className="h-0.5 bg-line" aria-hidden>
            <div className="h-full bg-muted" style={{ width: formatPercent(confidence) }} />
          </div>
          <p className="mt-1 font-mono text-small text-muted tabular-nums">
            confiança {formatPercent(confidence)}
          </p>
        </div>
      )}
    </div>
  );
}

export function Chip({ children, value }: { children: ReactNode; value?: string }) {
  return (
    <span className="inline-flex items-baseline gap-2 rounded-sm bg-raised px-2 py-1 text-small">
      {children}
      {value && <span className="font-mono text-muted tabular-nums">{value}</span>}
    </span>
  );
}

type NoticeProps = { tone?: "info" | "danger"; onDismiss?: () => void; children: ReactNode };

export function Notice({ tone = "info", onDismiss, children }: NoticeProps) {
  const color = tone === "info" ? "border-info" : "border-danger";
  const title = tone === "info" ? "Aviso" : "Erro";
  return (
    <div
      role={tone === "danger" ? "alert" : "status"}
      className={`flex items-center justify-between gap-3 border-l-2 ${color} bg-surface px-3 py-2 text-small`}
    >
      <div>
        <span className={`mr-2 font-mono ${tone === "info" ? "text-info" : "text-danger"}`}>{title}</span>
        {children}
      </div>
      {onDismiss && (
        <button
          type="button"
          aria-label="Fechar aviso"
          onClick={onDismiss}
          className="flex size-8 shrink-0 cursor-pointer items-center justify-center rounded-sm text-muted transition-colors duration-100 hover:bg-raised hover:text-text"
        >
          <svg viewBox="0 0 16 16" className="size-3 stroke-current" strokeWidth={2} aria-hidden>
            <path d="M2 2l12 12M14 2L2 14" />
          </svg>
        </button>
      )}
    </div>
  );
}
