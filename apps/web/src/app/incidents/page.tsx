"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";
import { Badge, Button, Card, EmptyState, ErrorBox, Field, LoadingRows, PageHeader, input, link, td, th } from "@/components/ui";
import { useQueryState } from "@/lib/url";
import { api, errorText, post, type Incident, type Page } from "@/lib/api";

const empty = { title: "", severity: "SEV3", service: "", symptoms: "", environment: "", started_at: "", detected_at: "", log_excerpt: "" };
const SEVERITIES = ["SEV1", "SEV2", "SEV3", "SEV4"];

function IncidentsPage() {
  const router = useRouter();
  const [items, setItems] = useState<Incident[] | null>(null);
  const [form, setForm] = useState(empty);
  const [error, setError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [creating, setCreating] = useQueryState("new");
  const [query, setQuery] = useQueryState("q");
  const [severity, setSeverity] = useQueryState("severity", "all");

  useEffect(() => {
    api<Page<Incident>>("/incidents?limit=50")
      .then((p) => setItems(p.items))
      .catch((e) => setError(errorText(e)));
  }, []);

  const set = (k: keyof typeof empty) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    setForm({ ...form, [k]: e.target.value });

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setFormError(null);
    try {
      const body = Object.fromEntries(Object.entries(form).map(([k, v]) => [k, v === "" ? null : v]));
      if (body.started_at) body.started_at = new Date(body.started_at as string).toISOString();
      if (body.detected_at) body.detected_at = new Date(body.detected_at as string).toISOString();
      const inc = await post<Incident>("/incidents", body);
      router.push(`/incidents/${inc.id}`);
    } catch (err) {
      setFormError(errorText(err));
      setBusy(false);
    }
  }

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (items ?? []).filter(
      (i) => (severity === "all" || i.severity === severity) && (!q || i.title.toLowerCase().includes(q) || i.service.toLowerCase().includes(q)),
    );
  }, [items, query, severity]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Incidents"
        description="Record symptoms and sanitized logs, then get observations, suspected causes and read-only checks."
        actions={
          !creating && (
            <Button onClick={() => setCreating("1")}>
              New incident
            </Button>
          )
        }
      />
      <ErrorBox message={error} />
      {creating && (
        <Card title="New incident" description="Credentials, tokens, emails and public IPs in the log excerpt are redacted before storage.">
          <form className="max-w-3xl space-y-5" onSubmit={create}>
          {formError && <ErrorBox message={formError} />}
          <fieldset className="grid gap-4 sm:grid-cols-2">
            <legend className="visually-hidden">Basics</legend>
            <Field label="Title" className="sm:col-span-2">
              {(p) => <input {...p} className={input} value={form.title} onChange={set("title")} required maxLength={200} placeholder="Checkout returns HTTP 502" />}
            </Field>
            <Field label="Severity">
              {(p) => (
                <select {...p} className={input} value={form.severity} onChange={set("severity")}>
                  {SEVERITIES.map((s) => (
                    <option key={s}>{s}</option>
                  ))}
                </select>
              )}
            </Field>
            <Field label="Service">
              {(p) => <input {...p} className={input} value={form.service} onChange={set("service")} required placeholder="checkout-web" />}
            </Field>
            <Field label="Environment" hint="Optional">
              {(p) => <input {...p} className={input} value={form.environment} onChange={set("environment")} placeholder="production" />}
            </Field>
            <div className="hidden sm:block" />
            <Field label="Started at" hint="Optional">
              {(p) => <input {...p} className={input} type="datetime-local" value={form.started_at} onChange={set("started_at")} />}
            </Field>
            <Field label="Detected at" hint="Optional">
              {(p) => <input {...p} className={input} type="datetime-local" value={form.detected_at} onChange={set("detected_at")} />}
            </Field>
          </fieldset>
          <Field label="Symptoms" hint="What users or monitors observed.">
            {(p) => <textarea {...p} className={input} rows={3} value={form.symptoms} onChange={set("symptoms")} required />}
          </Field>
          <Field label="Log excerpt" hint={`Optional, treated as untrusted data. ${form.log_excerpt.length.toLocaleString()} of 20,000 characters.`}>
            {(p) => (
              <textarea {...p} className={`${input} measured`} rows={8} value={form.log_excerpt} onChange={set("log_excerpt")} maxLength={20000} />
            )}
          </Field>
            <div className="flex flex-wrap gap-2">
              <Button type="submit" loading={busy}>
                {busy ? "Creating…" : "Create incident"}
              </Button>
              <Button variant="secondary" onClick={() => setCreating("")}>
                Cancel
              </Button>
            </div>
          </form>
        </Card>
      )}
      <div className="flex flex-col gap-2 sm:flex-row">
        <input className={`${input} sm:max-w-sm`} type="search" placeholder="Search title or service" value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Search incidents" />
        <select className={`${input} sm:w-44`} value={severity} onChange={(e) => setSeverity(e.target.value)} aria-label="Filter by severity">
          <option value="all">All severities</option>
          {SEVERITIES.map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
      </div>
      {items === null ? (
        !error && <LoadingRows rows={4} label="Loading incidents" />
      ) : items.length === 0 ? (
        <EmptyState
          title="No incidents yet"
          description="An incident holds the symptoms and sanitized logs for one investigation. Create one to start a structured analysis."
          action={
            !creating && (
              <Button variant="secondary" size="sm" onClick={() => setCreating("1")}>
                New incident
              </Button>
            )
          }
        />
      ) : visible.length === 0 ? (
        <EmptyState title="No matching incidents" description="Try a different search or severity." />
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr>
              <th className={th}>Severity</th>
              <th className={th}>Incident</th>
              <th className={`${th} max-md:hidden`}>Environment</th>
              <th className={th}>Status</th>
              <th className={`${th} max-md:hidden`}>Created</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((i) => (
              <tr key={i.id}>
                <td className={td}>
                  <Badge value={i.severity} />
                </td>
                <td className={`${td} [overflow-wrap:anywhere]`}>
                  <Link href={`/incidents/${i.id}`} className={`${link} text-ink`}>
                    {i.title}
                  </Link>
                  <p className="mt-0.5 text-muted">{i.service}</p>
                  <p className="measured mt-0.5 text-xs text-muted md:hidden">{new Date(i.created_at).toLocaleString()}</p>
                </td>
                <td className={`${td} text-ink-2 max-md:hidden`}>{i.environment ?? "–"}</td>
                <td className={td}>
                  <Badge value={i.status} />
                </td>
                <td className={`${td} measured whitespace-nowrap text-ink-2 max-md:hidden`}>{new Date(i.created_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export default function Incidents() {
  return (
    <Suspense>
      <IncidentsPage />
    </Suspense>
  );
}
