"use client";

import { useEffect, useId, useRef, type ReactNode } from "react";
import { Icon, type IconName } from "./icons";

export const cx = (...xs: (string | false | null | undefined)[]) => xs.filter(Boolean).join(" ");

type Variant = "primary" | "secondary" | "ghost" | "danger";
// Amber is the person's one move on a screen; everything else is a quiet outline.
const variants: Record<Variant, string> = {
  primary: "bg-accent text-accent-ink hover:bg-accent-2 active:bg-ink",
  secondary: "border border-rule-2 text-ink hover:border-muted hover:bg-rule/40 active:bg-rule",
  ghost: "text-ink-2 hover:bg-rule/50 hover:text-ink active:bg-rule",
  danger: "border border-rule-2 text-bad hover:border-bad hover:bg-bad-soft active:bg-rule",
};
const sizes = { sm: "h-8 gap-1.5 px-3", md: "h-9 gap-2 px-4" };

export const btn = (variant: Variant = "primary", size: keyof typeof sizes = "md") =>
  cx(
    // The pseudo-element lifts the hit target to 44px without growing the control.
    "relative inline-flex shrink-0 items-center justify-center whitespace-nowrap rounded-pill text-sm font-medium transition-colors duration-[var(--dur-micro)] before:absolute before:inset-x-0 before:-inset-y-1.5 disabled:pointer-events-none disabled:opacity-45",
    variants[variant],
    sizes[size],
  );
export const input =
  "block min-h-9 w-full rounded-pill border border-edge bg-paper-3 px-3 py-1.5 text-sm text-ink transition-colors duration-[var(--dur-micro)] placeholder:text-muted hover:border-muted focus:border-accent disabled:opacity-45 aria-[invalid=true]:border-bad";
export const link = "underline decoration-rule-2 underline-offset-[0.2em] transition-colors hover:text-accent hover:decoration-accent";

export function Spinner({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={cx("spin", className)} aria-hidden="true">
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
  return <div className={cx("skeleton", className)} aria-hidden="true" />;
}

export function LoadingRows({ rows = 3, label = "Loading" }: { rows?: number; label?: string }) {
  return (
    <div className="space-y-3 py-2" role="status" aria-label={label}>
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} className={cx("h-4", i % 2 ? "w-2/3" : "w-full")} />
      ))}
    </div>
  );
}

const SectionHead = ({ title, description, actions }: { title?: ReactNode; description?: ReactNode; actions?: ReactNode }) =>
  title || actions ? (
    <header className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
      <div className="min-w-0">
        {title && <h2>{title}</h2>}
        {description && <p className="mt-1.5 max-w-[65ch] text-sm text-muted">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </header>
  ) : null;

/** A hairline panel: one bordered surface, a step lighter than the page. Never nest one in another. */
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
    <section className={cx("min-w-0 rounded-card border border-rule bg-paper-2", className)}>
      {(title || actions) && (
        <div className="border-b border-rule px-5 py-4">
          <SectionHead title={title} description={description} actions={actions} />
        </div>
      )}
      <div className={flush ? "" : "p-5"}>{children}</div>
    </section>
  );
}

/** A titled region straight on the page, for tables and trails that need no box. */
export function Section({
  title,
  description,
  actions,
  children,
  className,
}: {
  title?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={cx("min-w-0 space-y-4", className)}>
      <SectionHead title={title} description={description} actions={actions} />
      {children}
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
    <div className="mb-8 space-y-3">
      {crumbs}
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-4">
        <div className="min-w-0">
          <h1>{title}</h1>
          {description && <p className="mt-3 max-w-[65ch] text-ink-2">{description}</p>}
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
      <label htmlFor={fid} className="block text-sm text-ink-2">
        {label}
      </label>
      {children({ id: fid, "aria-describedby": describedBy, "aria-invalid": error ? true : undefined })}
      {hint && !error && (
        <p id={`${fid}-hint`} className="text-xs text-muted">
          {hint}
        </p>
      )}
      {error && (
        <p id={`${fid}-err`} className="text-xs text-error">
          {error}
        </p>
      )}
    </div>
  );
}

// person = waiting on or done by a human (amber); instrument = written by the system (cool).
type Tone = "neutral" | "ok" | "bad" | "person" | "instrument";
const toneClass: Record<Tone, string> = {
  neutral: "border-rule-2 text-ink-2",
  ok: "border-ok-soft bg-ok-soft text-ok",
  bad: "border-bad-soft bg-bad-soft text-bad",
  person: "border-accent-soft bg-accent-soft text-accent",
  instrument: "border-cool-soft bg-cool-soft text-cool",
};
const valueTone: Record<string, Tone> = {
  ready: "ok",
  CONFIRMED: "ok",
  REVIEWED: "ok",
  resolved: "ok",
  failed: "bad",
  SEV1: "bad",
  UNCONFIRMED: "person",
  DRAFT: "person",
  open: "person",
  suspected: "instrument",
  queued: "instrument",
  processing: "instrument",
  investigating: "instrument",
};
const label = (v: string) => (/^[a-z]/.test(v) ? v.charAt(0).toUpperCase() + v.slice(1) : v);

/** A chip carries state only: text in a hairline box, no dot. */
export function Badge({ value, tone, children }: { value: string; tone?: Tone; children?: ReactNode }) {
  return (
    <span className={cx("inline-flex items-center gap-1 whitespace-nowrap rounded-chip border px-1.5 py-px text-xs", toneClass[tone ?? valueTone[value] ?? "neutral"])}>
      {children ?? label(value)}
    </span>
  );
}

export function AiLabel() {
  return (
    <span title="Generated by a language model; verify before acting">
      <Badge value="AI-generated" tone="instrument" />
    </span>
  );
}

const alertTone = {
  info: ["border-rule bg-paper-2", "info", "text-cool"],
  warning: ["border-accent-soft bg-accent-soft", "alert", "text-accent"],
  danger: ["border-bad-soft bg-bad-soft", "alert", "text-bad"],
  success: ["border-ok-soft bg-ok-soft", "check", "text-ok"],
} as const;

export function Alert({ tone = "info", title, children }: { tone?: keyof typeof alertTone; title?: ReactNode; children?: ReactNode }) {
  const [cls, icon, iconCls] = alertTone[tone];
  return (
    <div role={tone === "danger" ? "alert" : "status"} className={cx("flex gap-3 rounded-card border px-4 py-3 text-sm text-ink", cls)}>
      <Icon name={icon} className={cx("mt-0.5 h-4 w-4", iconCls)} />
      <div className="min-w-0 space-y-0.5">
        {title && <p className="font-medium">{title}</p>}
        {children && <div className="break-words text-ink-2">{children}</div>}
      </div>
    </div>
  );
}

export function ErrorBox({ message }: { message: string | null }) {
  if (!message) return null;
  return <Alert tone="danger">{message}</Alert>;
}

/** Says what belongs here, why it is empty and the one way to fill it. */
export function EmptyState({ title, description, action }: { title: ReactNode; description?: ReactNode; action?: ReactNode }) {
  return (
    <div className="border-y border-rule py-8">
      <p className="font-medium text-ink">{title}</p>
      {description && <p className="mt-1 max-w-[60ch] text-sm text-muted">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="py-2 text-sm text-muted">{children}</p>;
}

/** A figure and its label. Sits inside a `.panels` grid, never in its own card. */
export function StatCard({ label, value, hint }: { label: string; value: ReactNode; hint?: ReactNode }) {
  return (
    <div className="px-5 py-4">
      <p className="text-sm text-muted">{label}</p>
      <p className="measured mt-1 text-xl text-ink">{value}</p>
      {hint && <p className="mt-1 text-xs text-muted">{hint}</p>}
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
        "m-auto max-h-[90dvh] w-[calc(100%-2rem)] overflow-hidden rounded-card border border-rule-2 bg-paper-2 p-0",
        wide ? "max-w-3xl" : "max-w-md",
      )}
    >
      {open && (
        <div className="flex max-h-[90dvh] flex-col">
          <header className="flex items-start justify-between gap-3 border-b border-rule px-5 py-4">
            <div>
              <h2 id={titleId}>
                {title}
              </h2>
              {description && <p className="mt-1.5 text-sm text-muted">{description}</p>}
            </div>
            <button className={btn("ghost", "sm")} onClick={onClose} aria-label="Close dialog">
              <Icon name="x" />
            </button>
          </header>
          {children && <div className="overflow-y-auto px-5 py-4">{children}</div>}
          {footer && <footer className="flex flex-wrap justify-end gap-2 border-t border-rule px-5 py-4">{footer}</footer>}
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
    <div role="tablist" aria-label={label} className="flex gap-1 overflow-x-auto overflow-y-hidden border-b border-rule">
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
              "-mb-px flex h-10 items-center gap-2 whitespace-nowrap border-b-2 px-3 text-sm transition-colors duration-[var(--dur-micro)] active:text-accent",
              active ? "border-ink text-ink" : "border-transparent text-muted hover:text-ink",
            )}
          >
            {t.label}
            {t.count !== undefined && (
              <span className="measured text-xs text-muted">{t.count}</span>
            )}
          </button>
        );
      })}
    </div>
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
      <mark className="rounded-chip bg-cool-soft px-0.5 text-ink">{text.slice(match.index, end)}</mark>
      {text.slice(end)}
    </span>
  );
}

// Tables sit straight on the page: sentence-case heads, horizontal rules only.
export const th = "whitespace-nowrap border-b border-rule-2 py-2 pr-3 text-left text-sm font-normal text-muted last:pr-0 sm:pr-6";
export const td = "border-b border-rule py-3 pr-3 align-top last:pr-0 sm:pr-6";
