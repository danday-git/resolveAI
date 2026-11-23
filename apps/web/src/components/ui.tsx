"use client";

import { createContext, useCallback, useContext, useEffect, useId, useRef, useState, type ReactNode } from "react";
import { Icon, type IconName } from "./icons";

export const cx = (...xs: (string | false | null | undefined)[]) => xs.filter(Boolean).join(" ");

type Variant = "primary" | "secondary" | "ghost" | "danger";
const variants: Record<Variant, string> = {
  primary: "bg-indigo-600 text-white shadow-xs hover:bg-indigo-700 active:bg-indigo-800",
  secondary: "border border-zinc-300 bg-white text-zinc-800 shadow-xs hover:bg-zinc-50 active:bg-zinc-100",
  ghost: "text-zinc-700 hover:bg-zinc-100 active:bg-zinc-200",
  danger: "border border-red-200 bg-white text-red-700 hover:bg-red-50 active:bg-red-100",
};
const sizes = { sm: "h-8 gap-1.5 px-2.5 text-xs", md: "h-9 gap-2 px-3.5 text-sm" };

export const btn = (variant: Variant = "primary", size: keyof typeof sizes = "md") =>
  cx(
    "inline-flex shrink-0 items-center justify-center whitespace-nowrap rounded-control font-medium transition-colors disabled:pointer-events-none disabled:opacity-50",
    variants[variant],
    sizes[size],
  );
export const button = btn("primary");
export const buttonSecondary = btn("secondary");
export const input =
  "block w-full rounded-control border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 shadow-xs transition-colors placeholder:text-zinc-400 hover:border-zinc-400 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 disabled:bg-zinc-50 aria-[invalid=true]:border-red-400";

export function Spinner({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={cx("animate-spin", className)} aria-hidden="true">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="3" fill="none" opacity=".25" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" fill="none" strokeLinecap="round" />
    </svg>
  );
}

export function Button({
  variant = "primary",
  size = "md",
  icon,
  loading,
  children,
  className,
  disabled,
  type = "button",
  ...rest
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: "sm" | "md"; icon?: IconName; loading?: boolean }) {
  return (
    <button type={type} className={cx(btn(variant, size), className)} disabled={disabled || loading} aria-busy={loading || undefined} {...rest}>
      {loading ? <Spinner /> : icon && <Icon name={icon} />}
      {children}
    </button>
  );
}

export function Skeleton({ className = "h-4 w-full" }: { className?: string }) {
  return <div className={cx("animate-pulse rounded bg-zinc-200/70", className)} aria-hidden="true" />;
}

export function LoadingRows({ rows = 3, label = "Loading" }: { rows?: number; label?: string }) {
  return (
    <div className="space-y-3" role="status" aria-label={label}>
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} className={cx("h-4", i % 2 ? "w-2/3" : "w-full")} />
      ))}
    </div>
  );
}

export function Card({
  title,
  description,
  children,
  actions,
  className,
  flush,
}: {
  title?: ReactNode;
  description?: ReactNode;
  children: ReactNode;
  actions?: ReactNode;
  className?: string;
  flush?: boolean;
}) {
  return (
    <section className={cx("min-w-0 rounded-card border border-zinc-200 bg-white", className)}>
      {(title || actions) && (
        <header className="flex flex-wrap items-start justify-between gap-3 border-b border-zinc-100 px-4 py-3 sm:px-5">
          <div className="min-w-0">
            {title && <h2 className="text-sm font-semibold text-zinc-900">{title}</h2>}
            {description && <p className="mt-0.5 text-xs text-zinc-500">{description}</p>}
          </div>
          {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className={flush ? "" : "p-4 sm:p-5"}>{children}</div>
    </section>
  );
}

export function PageHeader({
  title,
  description,
  actions,
  crumbs,
}: {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  crumbs?: ReactNode;
}) {
  return (
    <div className="mb-6 space-y-2">
      {crumbs}
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-xl font-semibold tracking-tight text-zinc-950 sm:text-2xl">{title}</h1>
          {description && <p className="mt-1 max-w-2xl text-sm text-zinc-500">{description}</p>}
        </div>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
    </div>
  );
}

export function Field({
  label,
  hint,
  error,
  children,
  id,
  className,
}: {
  label: ReactNode;
  hint?: ReactNode;
  error?: string | null;
  children: (props: { id: string; "aria-describedby"?: string; "aria-invalid"?: boolean }) => ReactNode;
  id?: string;
  className?: string;
}) {
  const auto = useId();
  const fid = id ?? auto;
  const describedBy = [hint && `${fid}-hint`, error && `${fid}-err`].filter(Boolean).join(" ") || undefined;
  return (
    <div className={cx("space-y-1.5", className)}>
      <label htmlFor={fid} className="block text-sm font-medium text-zinc-800">
        {label}
      </label>
      {children({ id: fid, "aria-describedby": describedBy, "aria-invalid": error ? true : undefined })}
      {hint && !error && (
        <p id={`${fid}-hint`} className="text-xs text-zinc-500">
          {hint}
        </p>
      )}
      {error && (
        <p id={`${fid}-err`} className="text-xs text-red-600">
          {error}
        </p>
      )}
    </div>
  );
}

type Tone = "neutral" | "success" | "warning" | "danger" | "orange" | "info" | "ai";
const toneClass: Record<Tone, string> = {
  neutral: "bg-zinc-100 text-zinc-700 ring-zinc-200",
  success: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  warning: "bg-amber-50 text-amber-800 ring-amber-200",
  danger: "bg-red-50 text-red-700 ring-red-200",
  orange: "bg-orange-50 text-orange-700 ring-orange-200",
  info: "bg-sky-50 text-sky-700 ring-sky-200",
  ai: "bg-violet-50 text-violet-700 ring-violet-200",
};
const dotClass: Record<Tone, string> = {
  neutral: "bg-zinc-400",
  success: "bg-emerald-500",
  warning: "bg-amber-500",
  danger: "bg-red-500",
  orange: "bg-orange-500",
  info: "bg-sky-500",
  ai: "bg-violet-500",
};
const valueTone: Record<string, Tone> = {
  ready: "success",
  CONFIRMED: "success",
  REVIEWED: "success",
  resolved: "success",
  failed: "danger",
  SEV1: "danger",
  SEV2: "orange",
  SEV3: "warning",
  UNCONFIRMED: "warning",
  DRAFT: "warning",
  suspected: "warning",
  high: "orange",
  medium: "warning",
  queued: "info",
  processing: "info",
  investigating: "info",
  open: "info",
};
const label = (v: string) => (/^[a-z]/.test(v) ? v.charAt(0).toUpperCase() + v.slice(1) : v);

export function Badge({ value, tone, dot = true, children }: { value: string; tone?: Tone; dot?: boolean; children?: ReactNode }) {
  const t = tone ?? valueTone[value] ?? "neutral";
  return (
    <span className={cx("inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset", toneClass[t])}>
      {dot && <span className={cx("h-1.5 w-1.5 rounded-full", dotClass[t])} aria-hidden="true" />}
      {children ?? label(value)}
    </span>
  );
}

export function AiLabel() {
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full bg-violet-50 px-2 py-0.5 text-xs font-medium text-violet-700 ring-1 ring-inset ring-violet-200"
      title="Generated by a language model; verify before acting"
    >
      <Icon name="sparkle" className="h-3 w-3" />
      AI-generated
    </span>
  );
}

const alertTone = {
  info: ["border-sky-200 bg-sky-50 text-sky-900", "info"],
  warning: ["border-amber-200 bg-amber-50 text-amber-900", "alert"],
  danger: ["border-red-200 bg-red-50 text-red-800", "alert"],
  success: ["border-emerald-200 bg-emerald-50 text-emerald-900", "check"],
} as const;

export function Alert({ tone = "info", title, children }: { tone?: keyof typeof alertTone; title?: ReactNode; children?: ReactNode }) {
  const [cls, icon] = alertTone[tone];
  return (
    <div role={tone === "danger" ? "alert" : "status"} className={cx("flex gap-3 rounded-card border p-3 text-sm", cls)}>
      <Icon name={icon} className="mt-0.5 h-4 w-4" />
      <div className="min-w-0 space-y-0.5">
        {title && <p className="font-medium">{title}</p>}
        {children && <div className="break-words">{children}</div>}
      </div>
    </div>
  );
}

export function ErrorBox({ message }: { message: string | null }) {
  if (!message) return null;
  return <Alert tone="danger">{message}</Alert>;
}

export function EmptyState({
  icon = "info",
  title,
  description,
  action,
}: {
  icon?: IconName;
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center rounded-card border border-dashed border-zinc-300 px-4 py-8 text-center">
      <span className="mb-3 grid h-10 w-10 place-items-center rounded-full bg-zinc-100 text-zinc-500">
        <Icon name={icon} className="h-5 w-5" />
      </span>
      <p className="text-sm font-medium text-zinc-800">{title}</p>
      {description && <p className="mt-1 max-w-sm text-sm text-zinc-500">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <EmptyState title={children} />;
}

export function StatCard({ label, value, hint, icon }: { label: string; value: ReactNode; hint?: ReactNode; icon?: IconName }) {
  return (
    <div className="rounded-card border border-zinc-200 bg-white p-4">
      <div className="flex items-center justify-between gap-2 text-xs font-medium text-zinc-500">
        {label}
        {icon && <Icon name={icon} className="h-4 w-4 text-zinc-400" />}
      </div>
      <p className="mt-2 text-2xl font-semibold tabular-nums tracking-tight text-zinc-950">{value}</p>
      {hint && <p className="mt-1 text-xs text-zinc-500">{hint}</p>}
    </div>
  );
}

export function Dialog({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  wide,
}: {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  description?: ReactNode;
  children?: ReactNode;
  footer?: ReactNode;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);
  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      onClose={onClose}
      onClick={(e) => e.target === ref.current && onClose()}
      className={cx(
        "m-auto max-h-[90dvh] w-[calc(100%-2rem)] overflow-hidden rounded-card border border-zinc-200 bg-white p-0 text-zinc-900 shadow-xl backdrop:bg-zinc-950/40",
        wide ? "max-w-3xl" : "max-w-md",
      )}
    >
      {open && (
        <div className="flex max-h-[90dvh] flex-col">
          <header className="flex items-start justify-between gap-3 border-b border-zinc-100 px-5 py-4">
            <div>
              <h2 id={titleId} className="text-base font-semibold">
                {title}
              </h2>
              {description && <p className="mt-0.5 text-sm text-zinc-500">{description}</p>}
            </div>
            <button className={btn("ghost", "sm")} onClick={onClose} aria-label="Close dialog">
              <Icon name="x" />
            </button>
          </header>
          {children && <div className="overflow-y-auto px-5 py-4">{children}</div>}
          {footer && <footer className="flex flex-wrap justify-end gap-2 border-t border-zinc-100 bg-zinc-50 px-5 py-3">{footer}</footer>}
        </div>
      )}
    </dialog>
  );
}

export function Tabs<T extends string>({
  tabs,
  value,
  onChange,
  label,
}: {
  tabs: { id: T; label: string; count?: number }[];
  value: T;
  onChange: (id: T) => void;
  label: string;
}) {
  return (
    <div role="tablist" aria-label={label} className="-mb-px flex gap-1 overflow-x-auto border-b border-zinc-200">
      {tabs.map((t, i) => {
        const active = t.id === value;
        return (
          <button
            key={t.id}
            role="tab"
            id={`tab-${t.id}`}
            aria-selected={active}
            aria-controls={`panel-${t.id}`}
            tabIndex={active ? 0 : -1}
            onClick={() => onChange(t.id)}
            onKeyDown={(e) => {
              if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
              const next = tabs[(i + (e.key === "ArrowRight" ? 1 : tabs.length - 1)) % tabs.length];
              onChange(next.id);
              document.getElementById(`tab-${next.id}`)?.focus();
            }}
            className={cx(
              "flex items-center gap-2 whitespace-nowrap border-b-2 px-3 py-2.5 text-sm font-medium transition-colors",
              active ? "border-indigo-600 text-zinc-950" : "border-transparent text-zinc-500 hover:text-zinc-800",
            )}
          >
            {t.label}
            {t.count !== undefined && (
              <span className="rounded-full bg-zinc-100 px-1.5 text-xs tabular-nums text-zinc-600">{t.count}</span>
            )}
          </button>
        );
      })}
    </div>
  );
}

type Toast = { id: number; tone: "success" | "danger" | "info"; text: string };
const ToastContext = createContext<(tone: Toast["tone"], text: string) => void>(() => undefined);
export const useToast = () => useContext(ToastContext);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const push = useCallback((tone: Toast["tone"], text: string) => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, tone, text }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4500);
  }, []);
  return (
    <ToastContext.Provider value={push}>
      {children}
      <div aria-live="polite" className="pointer-events-none fixed inset-x-0 bottom-4 z-50 flex flex-col items-center gap-2 px-4 sm:items-end">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={cx(
              "pointer-events-auto flex max-w-sm items-start gap-2 rounded-card border bg-white px-4 py-3 text-sm shadow-lg",
              t.tone === "danger" ? "border-red-200 text-red-800" : "border-zinc-200 text-zinc-800",
            )}
          >
            <Icon
              name={t.tone === "success" ? "check" : t.tone === "danger" ? "alert" : "info"}
              className={cx("mt-0.5 h-4 w-4", t.tone === "success" ? "text-emerald-600" : t.tone === "danger" ? "text-red-600" : "text-sky-600")}
            />
            {t.text}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function Highlight({ text, quote }: { text: string; quote: string }) {
  const words = quote.trim().split(/\s+/).filter(Boolean).map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  const match = words.length ? new RegExp(words.join("\\s+"), "i").exec(text) : null;
  if (!match) return <span className="whitespace-pre-wrap">{text}</span>;
  const end = match.index + match[0].length;
  return (
    <span className="whitespace-pre-wrap">
      {text.slice(0, match.index)}
      <mark className="rounded bg-amber-200/80 px-0.5 text-zinc-950">{text.slice(match.index, end)}</mark>
      {text.slice(end)}
    </span>
  );
}

export const th = "px-4 py-2.5 text-left text-xs font-medium text-zinc-500";
export const td = "px-4 py-3 align-middle";
