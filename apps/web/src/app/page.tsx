"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Icon } from "@/components/icons";
import { Badge, Card, EmptyState, ErrorBox, LoadingRows, PageHeader, Section, StatCard, btn, link, td, th } from "@/components/ui";
import { api, errorText, type DocumentMeta, type DocumentPage, type Incident, type Page } from "@/lib/api";
import type { MetricsSummary } from "./metrics/page";

const principles: [string, string][] = [
  ["Evidence first", "Answers come only from the runbooks and SOPs you upload. Each claim links to the exact passage, and a question without one is declined instead of guessed."],
  ["Possible causes are not facts", "An analysis keeps what the log shows apart from what might explain it, with read-only checks for you to run. ResolveAI never runs a command."],
  ["A person confirms", "An RCA stays a draft, marked UNCONFIRMED, until a reviewer records the confirmed cause and signs off."],
];

export default function Overview() {
  const [incidents, setIncidents] = useState<Page<Incident> | null>(null);
  const [docs, setDocs] = useState<DocumentPage | null>(null);
  const [metrics, setMetrics] = useState<MetricsSummary | null>(null);
  const [conversations, setConversations] = useState<number | null>(null);
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
    api<Page<unknown>>("/conversations?limit=1")
      .then((c) => setConversations(c.total))
      .catch(() => setConversations(0));
  }, []);

  const count = (...s: DocumentMeta["status"][]) => s.reduce((n, k) => n + (docs?.status_counts[k] ?? 0), 0);
  const cost = metrics?.llm.estimated_cost_usd;
  const kb = [
    ["Ready", count("ready"), "bg-ok"],
    ["Processing", count("queued", "processing"), "bg-cool"],
    ["Failed", count("failed"), "bg-bad"],
  ] as const;
  // shortcut: "analyzed" looks at the five newest incidents only; a status count from the API would cover all.
  const steps: [string, string, string, boolean | null][] = [
    ["/knowledge", "Upload a runbook or SOP", "PDF, TXT or Markdown. These are the only sources the assistant may cite.", !!docs?.total],
    ["/knowledge", "Wait until it is ready", "ResolveAI splits each document into passages it can search. Ready means it can be cited.", count("ready") > 0],
    ["/assistant", "Ask a question and open its source", "Every claim in an answer has a numbered source showing the exact text.", !!conversations],
    ["/incidents?new=1", "Record an incident", "Symptoms and a log excerpt. Secrets, tokens, emails and public IPs are removed first.", !!incidents?.total],
    ["/incidents", "Run an analysis", "Observations from the log, possible causes, and read-only checks to run yourself.", !!incidents?.items.some((i) => i.status !== "open")],
    ["/incidents", "Review the RCA draft and confirm it yourself", "Open an analyzed incident, then its RCA tab. Not tracked here.", null],
  ];
  const loaded = docs !== null && incidents !== null && conversations !== null;
  const remaining = steps.filter(([, , , done]) => done === false).length;

  return (
    <div className="space-y-12">
      <PageHeader
        title="Overview"
        description="ResolveAI helps support, NOC and infrastructure engineers investigate incidents with their own runbooks: answers show their sources, possible causes stay separate from facts, and a person confirms the root cause."
        actions={
          <>
            <Link href="/assistant" className={btn("secondary")}>
              <Icon name="chat" />
              Ask assistant
            </Link>
            <Link href="/incidents?new=1" className={btn("primary")}>
              <Icon name="plus" />
              New incident
            </Link>
          </>
        }
      />
      <ErrorBox message={error} />
      {loaded && remaining > 0 && <GettingStarted steps={steps} remaining={remaining} />}
      <div className="grid gap-x-[var(--gap-columns)] gap-y-12 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <Section
          title="Recent incidents"
          actions={
            <Link className={`${link} text-sm text-ink-2`} href="/incidents">
              View all
              <Icon name="chevronRight" className="ml-0.5 inline h-3.5 w-3.5 align-[-0.15em]" />
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
                  <Icon name="plus" />
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
              hint={metrics ? (cost === null ? "No price set for this provider" : `${metrics.llm.calls} model calls`) : undefined}
            />
          </div>
          <Card
            title="Knowledge base"
            actions={
              <Link className={`${link} text-sm text-ink-2`} href="/knowledge">
                Manage
                <Icon name="chevronRight" className="ml-0.5 inline h-3.5 w-3.5 align-[-0.15em]" />
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
      {loaded && remaining === 0 && <GettingStarted steps={steps} remaining={0} />}
    </div>
  );
}


function GettingStarted({ steps, remaining }: { steps: [string, string, string, boolean | null][]; remaining: number }) {
  return (
    <Section
      title={remaining ? "Getting started" : "How ResolveAI works"}
      description={remaining ? `${remaining} of ${steps.length - 1} steps left. Each step is ticked from your own data.` : "All tracked steps are done. Unlike a general chatbot, ResolveAI:"}
    >
      {remaining > 0 && (
        <ol className="border-t border-rule">
          {steps.map(([href, t, d, done], i) => (
            <li key={t} className="border-b border-rule">
              <Link href={href} className="grid grid-cols-[1.5rem_minmax(0,1fr)_auto] items-start gap-x-3 py-3 no-underline transition-colors duration-[var(--dur-micro)] hover:bg-rule/40 active:bg-rule">
                {done ? <Icon name="check" className="mt-0.5 h-4 w-4 text-ok" /> : <span className="measured mt-px text-sm text-muted">{i + 1}</span>}
                <span className="min-w-0">
                  <span className={done ? "block text-muted line-through decoration-rule-2" : "block text-ink"}>{t}</span>
                  <span className="mt-0.5 block text-sm text-muted">{d}</span>
                </span>
                <span className="flex items-center gap-1 text-sm text-muted">
                  {done ? "Done" : done === null ? "Manual" : "To do"}
                  <Icon name="chevronRight" className="h-3.5 w-3.5" />
                </span>
                <span className="visually-hidden">{done ? "(done)" : done === null ? "(not tracked)" : "(to do)"}</span>
              </Link>
            </li>
          ))}
        </ol>
      )}
      <dl className="panels mt-6 sm:grid-cols-3">
        {principles.map(([t, d]) => (
          <div key={t} className="px-5 py-4">
            <dt className="text-ink">{t}</dt>
            <dd className="mt-1 text-sm text-muted">{d}</dd>
          </div>
        ))}
      </dl>
    </Section>
  );
}
