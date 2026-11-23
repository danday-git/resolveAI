"use client";

import { useEffect, useState } from "react";
import { Card, Empty, ErrorBox } from "@/components/ui";
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
    estimated_cost_usd: number;
    by_provider_model: { provider: string; model: string; calls: number; input_tokens: number; output_tokens: number; estimated_cost_usd: number | null }[];
    by_day: { date: string; calls: number; tokens: number; estimated_cost_usd: number | null }[];
  };
  ingestion: { documents_total: number; failed: number; by_error_code: { code: string; count: number }[] };
  alerts: { error_rate_over_5pct_last_20: boolean; p95_over_10s: boolean; daily_budget_exceeded: boolean; daily_budget_usd: number };
};

type Trace = { type: "request" | "llm"; request_id: string; method?: string; route?: string; status_code?: number; duration_ms?: number; created_at: string };

const ms = (v: number | null) => (v === null ? "–" : `${Math.round(v)} ms`);

export default function Metrics() {
  const [m, setM] = useState<MetricsSummary | null>(null);
  const [traces, setTraces] = useState<Trace[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<MetricsSummary>("/metrics/summary").then(setM).catch((e) => setError(errorText(e)));
    api<{ items: Trace[] }>("/metrics/requests?limit=25")
      .then((r) => setTraces(r.items.filter((t) => t.type === "request")))
      .catch(() => undefined);
  }, []);

  if (error) return <ErrorBox message={error} />;
  if (!m) return <p className="text-sm text-slate-500">Loading…</p>;
  const maxTokens = Math.max(1, ...m.llm.by_day.map((d) => d.tokens));
  const alerts = [
    ["Error rate > 5% over last 20 requests", m.alerts.error_rate_over_5pct_last_20],
    ["p95 latency > 10 s", m.alerts.p95_over_10s],
    [`Daily spend > $${m.alerts.daily_budget_usd} budget`, m.alerts.daily_budget_exceeded],
  ] as const;

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Evaluation / Ops</h1>
      <p className="text-xs text-slate-500">Window {m.window.from} → {m.window.to}. Costs are estimates from configurable pricing tables. Offline evaluation reports live in <code>evals/reports/</code>.</p>
      <div className="grid gap-4 md:grid-cols-4">
        {[
          ["Requests", m.requests.total],
          ["Error rate", `${(m.requests.error_rate * 100).toFixed(1)}%`],
          ["p50 / p95", `${ms(m.requests.p50_ms)} / ${ms(m.requests.p95_ms)}`],
          ["LLM tokens (in/out)", `${m.llm.input_tokens} / ${m.llm.output_tokens}`],
          ["LLM calls", m.llm.calls],
          ["LLM p95", ms(m.llm.p95_ms)],
          ["Estimated cost", `$${m.llm.estimated_cost_usd.toFixed(4)} (estimate)`],
          ["Ingestion failures", `${m.ingestion.failed} / ${m.ingestion.documents_total}`],
        ].map(([k, v]) => (
          <Card key={k as string}>
            <p className="text-xs text-slate-500">{k}</p>
            <p className="text-lg font-semibold">{v}</p>
          </Card>
        ))}
      </div>
      <Card title="Alert thresholds (simulated, demo only — no paging)">
        <ul className="space-y-1 text-sm">
          {alerts.map(([label, on]) => (
            <li key={label} className="flex items-center gap-2">
              <span className={`h-2 w-2 rounded-full ${on ? "bg-red-500" : "bg-emerald-500"}`} />
              {label}: <span className={on ? "font-semibold text-red-700" : "text-slate-600"}>{on ? "ALERT" : "ok"}</span>
            </li>
          ))}
        </ul>
      </Card>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Tokens per day">
          {m.llm.by_day.length === 0 ? <Empty>No metrics available.</Empty> : (
            <ul className="space-y-1 text-xs">
              {m.llm.by_day.map((d) => (
                <li key={d.date} className="grid grid-cols-[90px_1fr_120px] items-center gap-2">
                  <span>{d.date}</span>
                  <span className="h-3 rounded bg-slate-700" style={{ width: `${(d.tokens / maxTokens) * 100}%` }} />
                  <span className="text-right">{d.tokens} tok · ${(d.estimated_cost_usd ?? 0).toFixed(4)}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card title="By provider / model">
          {m.llm.by_provider_model.length === 0 ? <Empty>No LLM calls yet.</Empty> : (
            <table className="w-full text-left text-xs">
              <thead className="text-slate-500"><tr><th>Provider</th><th>Model</th><th>Calls</th><th>In</th><th>Out</th><th>Est. $</th></tr></thead>
              <tbody>
                {m.llm.by_provider_model.map((r) => (
                  <tr key={r.provider + r.model} className="border-t border-slate-100">
                    <td className="py-1">{r.provider}</td><td>{r.model}</td><td>{r.calls}</td><td>{r.input_tokens}</td><td>{r.output_tokens}</td>
                    <td>{r.estimated_cost_usd === null ? "unknown" : r.estimated_cost_usd.toFixed(5)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
        <Card title="Top errors">
          {m.requests.top_errors.length === 0 && m.ingestion.by_error_code.length === 0 ? <Empty>No errors recorded.</Empty> : (
            <ul className="text-xs">
              {m.requests.top_errors.map((e) => <li key={e.code}>{e.code}: {e.count}</li>)}
              {m.ingestion.by_error_code.map((e) => <li key={`ing-${e.code}`}>ingestion {e.code}: {e.count}</li>)}
            </ul>
          )}
        </Card>
        <Card title="Recent request traces">
          {traces.length === 0 ? <Empty>No traces yet.</Empty> : (
            <table className="w-full text-left text-xs">
              <thead className="text-slate-500"><tr><th>Time</th><th>Route</th><th>Status</th><th>ms</th></tr></thead>
              <tbody>
                {traces.map((t, i) => (
                  <tr key={t.request_id + i} className="border-t border-slate-100" title={`request ${t.request_id}`}>
                    <td className="py-1">{new Date(t.created_at).toLocaleTimeString()}</td>
                    <td>{t.method} {t.route}</td><td>{t.status_code}</td><td>{t.duration_ms}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      </div>
    </div>
  );
}
