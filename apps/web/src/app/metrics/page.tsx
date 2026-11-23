"use client";

import { useEffect, useState } from "react";
import { Badge, Card, Empty, ErrorBox, LoadingRows, PageHeader, Section, StatCard, cx, td, th } from "@/components/ui";
import { api, errorText } from "@/lib/api";

export type MetricsSummary = {
  window: { from: string; to: string };
  requests: { total: number; errors: number; error_rate: number; p50_ms: number | null; p95_ms: number | null; top_errors: { code: string; count: number }[] };
  llm: {
    calls: number;
    errors: number;
    p50_ms: number | null;
    p95_ms: number | null;
    input_tokens: number;
    output_tokens: number;
    estimated_cost_usd: number | null;
    by_provider_model: { provider: string; model: string; calls: number; input_tokens: number; output_tokens: number; estimated_cost_usd: number | null }[];
    by_day: { date: string; calls: number; tokens: number; estimated_cost_usd: number | null }[];
  };
  ingestion: { documents_total: number; failed: number; by_error_code: { code: string; count: number }[] };
  alerts: { error_rate_over_5pct_last_20: boolean; p95_over_10s: boolean; daily_budget_exceeded: boolean; daily_budget_usd: number };
};

type Trace = { type: "request" | "llm"; request_id: string; method?: string; route?: string; status_code?: number; duration_ms?: number; created_at: string };

const ms = (v: number | null) => (v === null ? "–" : `${Math.round(v)}\u00a0ms`);
const usd = (v: number | null, digits = 4) => (v === null ? "Unknown" : `$${v.toFixed(digits)}`);
const n = (v: number) => v.toLocaleString();

export default function Metrics() {
  const [m, setM] = useState<MetricsSummary | null>(null);
  const [traces, setTraces] = useState<Trace[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<MetricsSummary>("/metrics/summary").then(setM).catch((e) => setError(errorText(e)));
    api<{ items: Trace[] }>("/metrics/requests?limit=25")
      .then((r) => setTraces(r.items.filter((t) => t.type === "request")))
      .catch(() => setTraces([]));
  }, []);

  const header = (
    <PageHeader
      title="Evaluation / Ops"
      description={
        m
          ? `${new Date(m.window.from).toLocaleDateString()} to ${new Date(m.window.to).toLocaleDateString()}. How your requests and AI calls performed. Latency is time to respond (p50 typical, p95 slowest 5%); tokens are the text sent to and returned by the model; cost is estimated from a price table and reads Unknown when the provider has no price. Offline answer-quality reports are produced by the evaluation script, not shown here.`
          : "Latency, errors, token usage and estimated spend from real request events."
      }
    />
  );
  if (error)
    return (
      <div>
        {header}
        <ErrorBox message={error} />
      </div>
    );
  if (!m)
    return (
      <div>
        {header}
        <LoadingRows rows={6} label="Loading metrics" />
      </div>
    );

  const maxTokens = Math.max(1, ...m.llm.by_day.map((d) => d.tokens));
  const alerts = [
    ["Error rate > 5% over last 20 requests", m.alerts.error_rate_over_5pct_last_20],
    ["p95 latency > 10 s", m.alerts.p95_over_10s],
    [`Daily spend > $${m.alerts.daily_budget_usd} budget`, m.alerts.daily_budget_exceeded],
  ] as const;
  const errors = [...m.requests.top_errors.map((e) => ({ ...e, kind: "request" })), ...m.ingestion.by_error_code.map((e) => ({ ...e, kind: "ingestion" }))];

  return (
    <div className="space-y-12">
      {header}
      <div className="panels lg:grid-cols-[22rem_minmax(0,1fr)]">
        <section aria-labelledby="req-h" className="p-5">
          <h2 id="req-h">Requests</h2>
          <p className="reading mt-6">{n(m.requests.total)}</p>
          <p className="mt-2 text-sm text-muted">{n(m.requests.errors)} errors</p>
          <dl className="mt-6 text-sm">
            {[
              ["Error rate", `${(m.requests.error_rate * 100).toFixed(1)}%`],
              ["Latency p50", ms(m.requests.p50_ms)],
              ["Latency p95", ms(m.requests.p95_ms)],
            ].map(([k, v]) => (
              <div key={k} className="flex items-baseline justify-between border-t border-rule py-2 last:pb-0">
                <dt className="text-ink-2">{k}</dt>
                <dd className="measured">{v}</dd>
              </div>
            ))}
          </dl>
        </section>
        <section aria-labelledby="tok-h" className="flex flex-col p-5">
          <h2 id="tok-h">Tokens per day</h2>
          {m.llm.by_day.length === 0 ? (
            <Empty>No model calls in this window yet. Ask the assistant or analyze an incident and the daily totals appear here.</Empty>
          ) : (
            <ol className="mt-6 flex min-h-44 flex-1 items-end gap-4 overflow-x-auto border-b border-rule-2" aria-label="Tokens per day">
              {m.llm.by_day.map((d) => (
                <li key={d.date} className="flex h-full min-w-12 flex-col items-center justify-end gap-1.5" title={`${d.date}: ${n(d.tokens)} tokens, ${usd(d.estimated_cost_usd)}`}>
                  <span className="measured text-xs text-ink-2">{n(d.tokens)}</span>
                  <span className="w-6 rounded-t-chip bg-cool" style={{ height: `${(d.tokens / maxTokens) * 100}%`, minHeight: 1 }} />
                  <span className="measured pb-1.5 text-xs text-muted">{d.date.slice(5)}</span>
                </li>
              ))}
            </ol>
          )}
        </section>
      </div>
      <Section title="Model usage">
        <div className="panels grid-cols-2 lg:grid-cols-4">
          <StatCard label="LLM calls" value={n(m.llm.calls)} hint={`${n(m.llm.errors)} errors, p95 ${ms(m.llm.p95_ms)}`} />
          <StatCard label="Input tokens" value={n(m.llm.input_tokens)} />
          <StatCard label="Output tokens" value={n(m.llm.output_tokens)} />
          <StatCard label="Estimated cost" value={usd(m.llm.estimated_cost_usd)} hint={`Ingestion failures ${m.ingestion.failed} / ${m.ingestion.documents_total}`} />
        </div>
        {m.llm.by_provider_model.length === 0 ? (
          <Empty>No AI calls yet. The provider and model appear here after your first question or analysis.</Empty>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr>
                  <th className={th}>Provider and model</th>
                  <th className={cx(th, "text-right")}>Calls</th>
                  <th className={cx(th, "text-right")}>Input</th>
                  <th className={cx(th, "text-right")}>Output</th>
                  <th className={cx(th, "text-right")}>Est. cost</th>
                </tr>
              </thead>
              <tbody>
                {m.llm.by_provider_model.map((r) => (
                  <tr key={r.provider + r.model}>
                    <td className={cx(td, "measured text-cool")}>
                      {r.provider}/{r.model}
                    </td>
                    <td className={cx(td, "measured text-right")}>{n(r.calls)}</td>
                    <td className={cx(td, "measured text-right")}>{n(r.input_tokens)}</td>
                    <td className={cx(td, "measured text-right")}>{n(r.output_tokens)}</td>
                    <td className={cx(td, "measured text-right")}>{usd(r.estimated_cost_usd, 5)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>
      <div className="grid gap-[var(--gap-columns)] lg:grid-cols-2">
        <Card title="Alert thresholds" description="Simulated for the demo. Nothing is paged.">
          <ul className="text-sm">
            {alerts.map(([label, on]) => (
              <li key={label} className="flex items-center justify-between gap-3 border-b border-rule py-2.5 first:pt-0 last:border-0 last:pb-0">
                <span className="text-ink-2">{label}</span>
                <Badge value={on ? "Alert" : "OK"} tone={on ? "bad" : "ok"} />
              </li>
            ))}
          </ul>
        </Card>
        <Card title="Top errors">
          {errors.length === 0 ? (
            <Empty>No errors recorded in this window.</Empty>
          ) : (
            <ul className="text-sm">
              {errors.map((e) => (
                <li key={e.kind + e.code} className="flex items-center justify-between gap-3 border-b border-rule py-2.5 first:pt-0 last:border-0 last:pb-0">
                  <span className="flex min-w-0 items-center gap-3">
                    <code className="measured truncate text-bad">{e.code}</code>
                    <span className="text-muted">{e.kind}</span>
                  </span>
                  <span className="measured">{n(e.count)}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
      <Section title="Recent request traces" description="Last 25 API requests, newest first.">
        {traces === null ? (
          <LoadingRows rows={4} label="Loading traces" />
        ) : traces.length === 0 ? (
          <Empty>No traces yet. Requests appear here as soon as the API serves them.</Empty>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr>
                <th className={th}>Time</th>
                <th className={th}>Route</th>
                <th className={th}>Status</th>
                <th className={cx(th, "text-right")}>Duration</th>
                <th className={cx(th, "max-lg:hidden")}>Request</th>
              </tr>
            </thead>
            <tbody>
              {traces.map((t, i) => (
                <tr key={t.request_id + i}>
                  <td className={cx(td, "measured text-ink-2 sm:whitespace-nowrap")}>{new Date(t.created_at).toLocaleTimeString()}</td>
                  <td className={cx(td, "measured break-all")}>
                    <span className="mr-2 text-muted">{t.method}</span>
                    {t.route}
                    <p className="mt-0.5 text-xs text-cool lg:hidden">{t.request_id}</p>
                  </td>
                  <td className={td}>
                    <Badge value={String(t.status_code)} tone={(t.status_code ?? 0) >= 500 ? "bad" : (t.status_code ?? 0) >= 400 ? "neutral" : "ok"} />
                  </td>
                  <td className={cx(td, "measured whitespace-nowrap text-right")}>{t.duration_ms}&nbsp;ms</td>
                  <td className={cx(td, "measured text-cool max-lg:hidden")}>{t.request_id}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Section>
    </div>
  );
}
