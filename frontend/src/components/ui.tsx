import type { ButtonHTMLAttributes, ReactNode } from "react";

import { formatPercent } from "../lib/format";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "ghost" };

export function Button({ variant = "ghost", className = "", ...props }: ButtonProps) {
  return <button type="button" className={`btn ${variant === "primary" ? "btn-primary" : ""} ${className}`} {...props} />;
}

type RoundButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & { label: string; large?: boolean; halo?: boolean };

export function RoundButton({ label, large, halo, className = "", ...props }: RoundButtonProps) {
  const look = `round ${large ? "round-lg" : ""} ${halo ? "halo" : ""} ${className}`;
  return <button type="button" aria-label={label} title={label} className={look} {...props} />;
}

export function Icon({ path, size = 20 }: { path: string; size?: number }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d={path} />
    </svg>
  );
}

export function Label({ children }: { children: ReactNode }) {
  return <span className="text-label font-medium tracking-label text-muted uppercase">{children}</span>;
}

type ReadoutProps = { label: string; value: string; detail?: string; confidence?: number };

export function Readout({ label, value, detail, confidence }: ReadoutProps) {
  return (
    <div>
      <Label>{label}</Label>
      <p className="text-readout font-semibold tracking-tight tabular-nums">{value}</p>
      {detail && <p className="text-small text-muted">{detail}</p>}
      {confidence !== undefined && (
        <div className="mt-2">
          <span className="meter" aria-hidden>
            <span style={{ width: formatPercent(confidence) }} />
          </span>
          <p className="mt-1 text-small text-muted tabular-nums">confiança {formatPercent(confidence)}</p>
        </div>
      )}
    </div>
  );
}

export function Chip({ children, value }: { children: ReactNode; value?: string }) {
  return (
    <span className="chip inline-flex items-baseline gap-2 px-3.5 py-1.5 text-small">
      {children}
      {value && <span className="text-muted tabular-nums">{value}</span>}
    </span>
  );
}

type NoticeProps = { tone?: "info" | "danger"; onDismiss?: () => void; children: ReactNode };

export function Notice({ tone = "info", onDismiss, children }: NoticeProps) {
  return (
    <div
      role={tone === "danger" ? "alert" : "status"}
      className={`well flex items-center justify-between gap-3 px-5 py-3 text-small ${tone === "danger" ? "text-danger" : ""}`}
    >
      <div>{children}</div>
      {onDismiss && (
        <button
          type="button"
          aria-label="Fechar aviso"
          onClick={onDismiss}
          className="flex size-8 shrink-0 cursor-pointer items-center justify-center rounded-full text-muted transition-colors duration-200 hover:text-accent"
        >
          <svg viewBox="0 0 16 16" className="size-3 stroke-current" strokeWidth={2} aria-hidden>
            <path d="M2 2l12 12M14 2L2 14" />
          </svg>
        </button>
      )}
    </div>
  );
}
