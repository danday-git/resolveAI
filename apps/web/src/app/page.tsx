"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Badge, Card, Empty, ErrorBox } from "@/components/ui";
import { api, errorText, type DocumentMeta, type Incident, type Page } from "@/lib/api";
import type { MetricsSummary } from "./metrics/page";

export default function Overview() {
  const [incidents, setIncidents] = useState<Incident[] | null>(null);
  const [docs, setDocs] = useState<Page<DocumentMeta> | null>(null);
  const [metrics, setMetrics] = useState<MetricsSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      api<Page<Incident>>("/incidents?limit=5"),
      api<Page<DocumentMeta>>("/documents?limit=100"),
      api<MetricsSummary>("/metrics/summary"),
    ])
      .then(([i, d, m]) => {
        setIncidents(i.items);
        setDocs(d);
        setMetrics(m);
      })
      .catch((e) => setError(errorText(e)));
  }, []);

  const count = (s: string) => docs?.items.filter((d) => d.status === s).length ?? 0;
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Overview</h1>
      <ErrorBox message={error} />
      <div className="grid gap-4 md:grid-cols-3">
        <Card title="Recent incidents" actions={<Link className="text-xs underline" href="/incidents">All</Link>}>
          {incidents === null ? (
            <p className="text-sm text-slate-500">Loading…</p>
          ) : incidents.length === 0 ? (
            <Empty>No incidents yet.</Empty>
          ) : (
            <ul className="space-y-2 text-sm">
              {incidents.map((i) => (
                <li key={i.id} className="flex items-center gap-2">
                  <Badge value={i.severity} />
                  <Link className="truncate hover:underline" href={`/incidents/${i.id}`}>{i.title}</Link>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card title="Ingestion status" actions={<Link className="text-xs underline" href="/knowledge">Manage</Link>}>
          {docs === null ? (
            <p className="text-sm text-slate-500">Loading…</p>
          ) : docs.total === 0 ? (
            <Empty>No documents uploaded.</Empty>
          ) : (
            <dl className="grid grid-cols-2 gap-2 text-sm">
              <dt>Ready</dt><dd className="text-right font-semibold">{count("ready")}</dd>
              <dt>Processing</dt><dd className="text-right font-semibold">{count("queued") + count("processing")}</dd>
              <dt>Failed</dt><dd className="text-right font-semibold">{count("failed")}</dd>
            </dl>
          )}
        </Card>
        <Card title="Last 7 days" actions={<Link className="text-xs underline" href="/metrics">Details</Link>}>
          {metrics === null ? (
            <p className="text-sm text-slate-500">Loading…</p>
          ) : metrics.requests.total === 0 ? (
            <Empty>No metrics available.</Empty>
          ) : (
            <dl className="grid grid-cols-2 gap-2 text-sm">
              <dt>Requests</dt><dd className="text-right font-semibold">{metrics.requests.total}</dd>
              <dt>Error rate</dt><dd className="text-right font-semibold">{(metrics.requests.error_rate * 100).toFixed(1)}%</dd>
              <dt>LLM calls</dt><dd className="text-right font-semibold">{metrics.llm.calls}</dd>
              <dt>Est. cost</dt><dd className="text-right font-semibold">${metrics.llm.estimated_cost_usd.toFixed(4)}</dd>
            </dl>
          )}
        </Card>
      </div>
    </div>
  );
}
