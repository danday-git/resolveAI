"use client";

import { useEffect, useState } from "react";
import { Badge, Card, EmptyState, ErrorBox, LoadingRows, PageHeader, StatCard, cx, td, th } from "@/components/ui";
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

const ms = (v: number | null) => (v === null ? "–" : `${Math.round(v)} ms`);
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
          ? `${new Date(m.window.from).toLocaleDateString()} – ${new Date(m.window.to).toLocaleDateString()} · costs are estimates from configurable pricing tables · offline evaluation reports live in evals/reports/`
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
    <div className="space-y-6">
      {header}
      <section aria-labelledby="req-h" className="space-y-3">
        <h2 id="req-h" className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
          Requests
        </h2>
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <StatCard label="Requests" icon="chart" value={n(m.requests.total)} hint={`${n(m.requests.errors)} errors`} />
          <StatCard label="Error rate" value={`${(m.requests.error_rate * 100).toFixed(1)}%`} />
          <StatCard label="Latency p50" value={ms(m.requests.p50_ms)} />
          <StatCard label="Latency p95" value={ms(m.requests.p95_ms)} />
        </div>
      </section>
      <section aria-labelledby="llm-h" className="space-y-3">
        <h2 id="llm-h" className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
          Model usage
        </h2>
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <StatCard label="LLM calls" icon="sparkle" value={n(m.llm.calls)} hint={`${n(m.llm.errors)} errors · p95 ${ms(m.llm.p95_ms)}`} />
          <StatCard label="Input tokens" value={n(m.llm.input_tokens)} />
          <StatCard label="Output tokens" value={n(m.llm.output_tokens)} />
          <StatCard label="Estimated cost" value={usd(m.llm.estimated_cost_usd)} hint={`Ingestion failures ${m.ingestion.failed} / ${m.ingestion.documents_total}`} />
        </div>
      </section>
      <div className="grid gap-5 lg:grid-cols-3">
        <Card title="Alert thresholds" description="Simulated, demo only — no paging.">
          <ul className="space-y-3 text-sm">
            {alerts.map(([label, on]) => (
              <li key={label} className="flex items-center justify-between gap-3">
                <span className="text-zinc-700">{label}</span>
                <Badge value={on ? "alert" : "ok"} tone={on ? "danger" : "success"}>
                  {on ? "Alert" : "OK"}
                </Badge>
              </li>
            ))}
          </ul>
        </Card>
        <Card title="Tokens per day" className="lg:col-span-2">
          {m.llm.by_day.length === 0 ? (
            <EmptyState icon="chart" title="No metrics available" description="Model calls will appear here." />
          ) : (
            <div className="flex h-44 items-end gap-2 overflow-x-auto" role="img" aria-label="Tokens per day bar chart">
              {m.llm.by_day.map((d) => (
                <div key={d.date} className="flex h-full min-w-12 flex-1 flex-col items-center justify-end gap-1.5" title={`${d.date}: ${n(d.tokens)} tokens · ${usd(d.estimated_cost_usd)}`}>
                  <span className="text-[11px] tabular-nums text-zinc-500">{n(d.tokens)}</span>
                  <span className="w-full max-w-14 rounded-t bg-indigo-500" style={{ height: `${Math.max(4, (d.tokens / maxTokens) * 100)}%` }} />
                  <span className="text-[11px] text-zinc-500">{d.date.slice(5)}</span>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
      <div className="grid gap-5 lg:grid-cols-2">
        <Card title="By provider / model" flush>
          {m.llm.by_provider_model.length === 0 ? (
            <div className="p-5">
              <EmptyState title="No LLM calls yet" />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b border-zinc-100 bg-zinc-50/60">
                  <tr>
                    <th className={th}>Provider / model</th>
                    <th className={cx(th, "text-right")}>Calls</th>
                    <th className={cx(th, "text-right")}>In</th>
                    <th className={cx(th, "text-right")}>Out</th>
                    <th className={cx(th, "text-right")}>Est. $</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-100">
                  {m.llm.by_provider_model.map((r) => (
                    <tr key={r.provider + r.model}>
                      <td className={td}>
                        <span className="font-medium text-zinc-900">{r.provider}</span>
                        <span className="block font-mono text-xs text-zinc-500">{r.model}</span>
                      </td>
                      <td className={cx(td, "text-right tabular-nums")}>{n(r.calls)}</td>
                      <td className={cx(td, "text-right tabular-nums")}>{n(r.input_tokens)}</td>
                      <td className={cx(td, "text-right tabular-nums")}>{n(r.output_tokens)}</td>
                      <td className={cx(td, "text-right tabular-nums")}>{r.estimated_cost_usd === null ? "Unknown" : r.estimated_cost_usd.toFixed(5)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
        <Card title="Top errors" flush>
          {errors.length === 0 ? (
            <div className="p-5">
              <EmptyState icon="check" title="No errors recorded" />
            </div>
          ) : (
            <ul className="divide-y divide-zinc-100 text-sm">
              {errors.map((e) => (
                <li key={e.kind + e.code} className="flex items-center justify-between gap-3 px-4 py-2.5 sm:px-5">
                  <span className="flex min-w-0 items-center gap-2">
                    <Badge value={e.kind} tone={e.kind === "ingestion" ? "orange" : "danger"} dot={false} />
                    <code className="truncate font-mono text-xs text-zinc-800">{e.code}</code>
                  </span>
                  <span className="tabular-nums text-zinc-600">{n(e.count)}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
      <Card title="Recent request traces" description="Last 25 API requests. Hover a row for its request ID." flush>
        {traces === null ? (
          <div className="p-5">
            <LoadingRows rows={4} />
          </div>
        ) : traces.length === 0 ? (
          <div className="p-5">
            <EmptyState title="No traces yet" />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] text-sm">
              <thead className="border-b border-zinc-100 bg-zinc-50/60">
                <tr>
                  <th className={th}>Time</th>
                  <th className={th}>Route</th>
                  <th className={th}>Status</th>
                  <th className={cx(th, "text-right")}>Duration</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {traces.map((t, i) => (
                  <tr key={t.request_id + i} title={`request ${t.request_id}`} className="hover:bg-zinc-50/60">
                    <td className={cx(td, "whitespace-nowrap text-xs text-zinc-500")}>{new Date(t.created_at).toLocaleTimeString()}</td>
                    <td className={td}>
                      <span className="mr-2 rounded bg-zinc-100 px-1.5 py-0.5 font-mono text-[11px] font-medium text-zinc-700">{t.method}</span>
                      <span className="font-mono text-xs text-zinc-800">{t.route}</span>
                    </td>
                    <td className={td}>
                      <Badge value={String(t.status_code)} tone={(t.status_code ?? 0) >= 500 ? "danger" : (t.status_code ?? 0) >= 400 ? "warning" : "success"} />
                    </td>
                    <td className={cx(td, "text-right tabular-nums")}>{t.duration_ms} ms</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
