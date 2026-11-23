"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Icon } from "@/components/icons";
import { Badge, Card, EmptyState, ErrorBox, LoadingRows, PageHeader, Skeleton, StatCard, btn, cx } from "@/components/ui";
import { api, errorText, type DocumentMeta, type Incident, type Page } from "@/lib/api";
import type { MetricsSummary } from "./metrics/page";

const steps: [string, string, string][] = [
  ["/knowledge", "Upload a runbook or SOP", "PDF, TXT or Markdown, indexed into searchable chunks."],
  ["/assistant", "Ask a grounded question", "Answers cite exact excerpts or abstain."],
  ["/incidents", "Analyze an incident", "Paste logs, review suspected causes and read-only checks."],
  ["/incidents", "Draft and confirm the RCA", "A human reviewer confirms the root cause, then export."],
];

export default function Overview() {
  const [incidents, setIncidents] = useState<Page<Incident> | null>(null);
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
        setIncidents(i);
        setDocs(d);
        setMetrics(m);
      })
      .catch((e) => setError(errorText(e)));
  }, []);

  const count = (...s: string[]) => docs?.items.filter((d) => s.includes(d.status)).length ?? 0;
  const loading = metrics === null && !error;
  const cost = metrics?.llm.estimated_cost_usd;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Overview"
        description="Knowledge base health, recent incidents and the last 7 days of usage."
        actions={
          <>
            <Link href="/assistant" className={btn("secondary")}>
              <Icon name="chat" /> Ask assistant
            </Link>
            <Link href="/incidents?new=1" className={btn("primary")}>
              <Icon name="plus" /> New incident
            </Link>
          </>
        }
      />
      <ErrorBox message={error} />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {loading ? (
          Array.from({ length: 4 }, (_, i) => (
            <div key={i} className="rounded-card border border-zinc-200 bg-white p-4">
              <Skeleton className="h-3 w-20" />
              <Skeleton className="mt-3 h-7 w-16" />
            </div>
          ))
        ) : (
          <>
            <StatCard label="Incidents" icon="alert" value={incidents?.total ?? "–"} hint="Owned by you" />
            <StatCard label="Documents ready" icon="book" value={docs ? `${count("ready")}/${docs.total}` : "–"} hint={`${count("failed")} failed`} />
            <StatCard
              label="Requests (7 days)"
              icon="chart"
              value={metrics?.requests.total ?? "–"}
              hint={metrics ? `${(metrics.requests.error_rate * 100).toFixed(1)}% error rate` : undefined}
            />
            <StatCard
              label="Est. LLM cost (7 days)"
              icon="sparkle"
              value={cost === null || cost === undefined ? "Unknown" : `$${cost.toFixed(4)}`}
              hint={metrics ? `${metrics.llm.calls} model calls` : undefined}
            />
          </>
        )}
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <Card
          className="lg:col-span-2"
          title="Recent incidents"
          actions={
            <Link className={btn("ghost", "sm")} href="/incidents">
              View all <Icon name="chevronRight" className="h-3.5 w-3.5" />
            </Link>
          }
          flush
        >
          {incidents === null ? (
            <div className="p-5">
              <LoadingRows />
            </div>
          ) : incidents.items.length === 0 ? (
            <div className="p-5">
              <EmptyState
                icon="alert"
                title="No incidents yet"
                description="Create an incident to get structured observations and suspected causes."
                action={
                  <Link href="/incidents?new=1" className={btn("primary", "sm")}>
                    <Icon name="plus" /> New incident
                  </Link>
                }
              />
            </div>
          ) : (
            <ul className="divide-y divide-zinc-100">
              {incidents.items.map((i) => (
                <li key={i.id}>
                  <Link href={`/incidents/${i.id}`} className="flex items-center gap-3 px-4 py-3 transition-colors hover:bg-zinc-50 sm:px-5">
                    <Badge value={i.severity} />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-zinc-900">{i.title}</p>
                      <p className="truncate text-xs text-zinc-500">
                        {i.service} · {new Date(i.created_at).toLocaleDateString()}
                      </p>
                    </div>
                    <Badge value={i.status} />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card
          title="Knowledge base"
          actions={
            <Link className={btn("ghost", "sm")} href="/knowledge">
              Manage <Icon name="chevronRight" className="h-3.5 w-3.5" />
            </Link>
          }
        >
          {docs === null ? (
            <LoadingRows />
          ) : docs.total === 0 ? (
            <EmptyState icon="book" title="No documents" description="Upload an SOP or runbook to ground answers." />
          ) : (
            <div className="space-y-4">
              <div className="flex h-2 overflow-hidden rounded-full bg-zinc-100" aria-hidden="true">
                <span className="bg-emerald-500" style={{ width: `${(count("ready") / docs.total) * 100}%` }} />
                <span className="bg-sky-500" style={{ width: `${(count("queued", "processing") / docs.total) * 100}%` }} />
                <span className="bg-red-500" style={{ width: `${(count("failed") / docs.total) * 100}%` }} />
              </div>
              <dl className="space-y-2 text-sm">
                {(
                  [
                    ["Ready", count("ready"), "bg-emerald-500"],
                    ["Processing", count("queued", "processing"), "bg-sky-500"],
                    ["Failed", count("failed"), "bg-red-500"],
                  ] as const
                ).map(([k, v, c]) => (
                  <div key={k} className="flex items-center justify-between">
                    <dt className="flex items-center gap-2 text-zinc-600">
                      <span className={cx("h-2 w-2 rounded-full", c)} />
                      {k}
                    </dt>
                    <dd className="font-medium tabular-nums">{v}</dd>
                  </div>
                ))}
              </dl>
            </div>
          )}
        </Card>
      </div>
      <Card title="Demo workflow" description="The end-to-end path from knowledge to a confirmed RCA.">
        <ol className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {steps.map(([href, t, d], i) => (
            <li key={t}>
              <Link href={href} className="group flex h-full gap-3 rounded-card border border-zinc-200 p-3 transition-colors hover:border-indigo-300 hover:bg-indigo-50/40">
                <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-zinc-100 text-xs font-semibold text-zinc-600 group-hover:bg-indigo-100 group-hover:text-indigo-700">
                  {i + 1}
                </span>
                <span>
                  <span className="block text-sm font-medium text-zinc-900">{t}</span>
                  <span className="mt-0.5 block text-xs text-zinc-500">{d}</span>
                </span>
              </Link>
            </li>
          ))}
        </ol>
      </Card>
    </div>
  );
}
