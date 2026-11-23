"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Badge, Card, EmptyState, ErrorBox, LoadingRows, PageHeader, Section, StatCard, btn, link, td, th } from "@/components/ui";
import { api, errorText, type DocumentMeta, type DocumentPage, type Incident, type Page } from "@/lib/api";
import type { MetricsSummary } from "./metrics/page";

const steps: [string, string, string][] = [
  ["/knowledge", "Upload a runbook or SOP", "PDF, TXT or Markdown, indexed into searchable chunks."],
  ["/assistant", "Ask a grounded question", "Answers cite exact excerpts or abstain."],
  ["/incidents", "Analyze an incident", "Paste logs, review suspected causes and read-only checks."],
  ["/incidents", "Draft and confirm the RCA", "A human reviewer confirms the root cause, then export."],
];

export default function Overview() {
  const [incidents, setIncidents] = useState<Page<Incident> | null>(null);
  const [docs, setDocs] = useState<DocumentPage | null>(null);
  const [metrics, setMetrics] = useState<MetricsSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      api<Page<Incident>>("/incidents?limit=5"),
      api<DocumentPage>("/documents?limit=1"),
      api<MetricsSummary>("/metrics/summary"),
    ])
      .then(([i, d, m]) => {
        setIncidents(i);
        setDocs(d);
        setMetrics(m);
      })
      .catch((e) => setError(errorText(e)));
  }, []);

  const count = (...s: DocumentMeta["status"][]) => s.reduce((n, k) => n + (docs?.status_counts[k] ?? 0), 0);
  const cost = metrics?.llm.estimated_cost_usd;
  const kb = [
    ["Ready", count("ready"), "bg-ok"],
    ["Processing", count("queued", "processing"), "bg-cool"],
    ["Failed", count("failed"), "bg-bad"],
  ] as const;

  return (
    <div className="space-y-12">
      <PageHeader
        title="Overview"
        description="Knowledge base health, recent incidents and the last 7 days of usage."
        actions={
          <>
            <Link href="/assistant" className={btn("secondary")}>
              Ask assistant
            </Link>
            <Link href="/incidents?new=1" className={btn("primary")}>
              New incident
            </Link>
          </>
        }
      />
      <ErrorBox message={error} />
      <div className="grid gap-x-[var(--gap-columns)] gap-y-12 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <Section
          title="Recent incidents"
          actions={
            <Link className={`${link} text-sm text-ink-2`} href="/incidents">
              View all
            </Link>
          }
        >
          {incidents === null ? (
            !error && <LoadingRows rows={5} />
          ) : incidents.items.length === 0 ? (
            <EmptyState
              title="No incidents yet"
              description="Create an incident to get structured observations and suspected causes."
              action={
                <Link href="/incidents?new=1" className={btn("secondary", "sm")}>
                  New incident
                </Link>
              }
            />
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr>
                  <th className={th}>Severity</th>
                  <th className={th}>Incident</th>
                  <th className={`${th} max-sm:hidden`}>Opened</th>
                  <th className={th}>Status</th>
                </tr>
              </thead>
              <tbody>
                {incidents.items.map((i) => (
                  <tr key={i.id}>
                    <td className={td}>
                      <Badge value={i.severity} />
                    </td>
                    <td className={`${td} [overflow-wrap:anywhere]`}>
                      <Link href={`/incidents/${i.id}`} className={`${link} text-ink`}>
                        {i.title}
                      </Link>
                      <p className="mt-0.5 text-muted">{i.service}</p>
                    </td>
                    <td className={`${td} measured whitespace-nowrap text-ink-2 max-sm:hidden`}>{new Date(i.created_at).toLocaleDateString()}</td>
                    <td className={td}>
                      <Badge value={i.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Section>
        <div className="space-y-6">
          <div className="panels grid-cols-2" aria-busy={metrics === null && !error}>
            <StatCard label="Incidents" value={incidents?.total ?? "–"} hint="Owned by you" />
            <StatCard label="Documents ready" value={docs ? `${count("ready")}/${docs.total}` : "–"} hint={`${count("failed")} failed`} />
            <StatCard
              label="Requests (7 days)"
              value={metrics?.requests.total ?? "–"}
              hint={metrics ? `${(metrics.requests.error_rate * 100).toFixed(1)}% error rate` : undefined}
            />
            <StatCard
              label="Est. LLM cost (7 days)"
              value={metrics === null ? "–" : cost === null || cost === undefined ? "Unknown" : `$${cost.toFixed(4)}`}
              hint={metrics ? `${metrics.llm.calls} model calls` : undefined}
            />
          </div>
          <Card
            title="Knowledge base"
            actions={
              <Link className={`${link} text-sm text-ink-2`} href="/knowledge">
                Manage
              </Link>
            }
          >
            {docs === null ? (
              !error && <LoadingRows />
            ) : docs.total === 0 ? (
              <p className="text-sm text-muted">No documents. Upload an SOP or runbook to ground answers.</p>
            ) : (
              <div className="space-y-4">
                <div className="flex h-2 gap-px overflow-hidden rounded-chip bg-rule" aria-hidden="true">
                  {kb.map(([k, v, c]) => (
                    <span key={k} className={c} style={{ width: `${(v / docs.total) * 100}%` }} />
                  ))}
                </div>
                <dl className="text-sm">
                  {kb.map(([k, v]) => (
                    <div key={k} className="flex items-baseline justify-between border-b border-rule py-2 last:border-0 last:pb-0">
                      <dt className="text-ink-2">{k}</dt>
                      <dd className="measured">{v}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            )}
          </Card>
        </div>
      </div>
      <Section title="Demo workflow" description="The end-to-end path from knowledge to a confirmed RCA.">
        <ol className="panels sm:grid-cols-2 lg:grid-cols-4">
          {steps.map(([href, t, d], i) => (
            <li key={t}>
              <Link href={href} className="block h-full px-5 py-4 no-underline transition-colors duration-[var(--dur-micro)] hover:bg-rule/40 active:bg-rule">
                <span className="measured text-muted">{i + 1}</span>
                <span className="mt-2 block text-ink">{t}</span>
                <span className="mt-1 block text-sm text-muted">{d}</span>
              </Link>
            </li>
          ))}
        </ol>
      </Section>
    </div>
  );
}

