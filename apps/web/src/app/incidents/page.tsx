"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";
import { Icon } from "@/components/icons";
import { Badge, Button, Card, Dialog, EmptyState, ErrorBox, Field, LoadingRows, PageHeader, cx, input, td, th } from "@/components/ui";
import { api, errorText, post, type Incident, type Page } from "@/lib/api";

const empty = { title: "", severity: "SEV3", service: "", symptoms: "", environment: "", started_at: "", detected_at: "", log_excerpt: "" };
const SEVERITIES = ["SEV1", "SEV2", "SEV3", "SEV4"];

function IncidentsPage() {
  const router = useRouter();
  const params = useSearchParams();
  const [items, setItems] = useState<Incident[] | null>(null);
  const [form, setForm] = useState(empty);
  const [error, setError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [creating, setCreating] = useState(params.get("new") === "1");
  const [query, setQuery] = useState("");
  const [severity, setSeverity] = useState("all");

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
          <Button icon="plus" onClick={() => setCreating(true)}>
            New incident
          </Button>
        }
      />
      <ErrorBox message={error} />
      <Card flush>
        <div className="flex flex-col gap-2 border-b border-zinc-100 p-3 sm:flex-row sm:items-center sm:px-4">
          <div className="relative flex-1">
            <Icon name="search" className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-400" />
            <input className={`${input} pl-9`} placeholder="Search title or service" value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Search incidents" />
          </div>
          <select className={`${input} sm:w-40`} value={severity} onChange={(e) => setSeverity(e.target.value)} aria-label="Filter by severity">
            <option value="all">All severities</option>
            {SEVERITIES.map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </div>
        {items === null ? (
          <div className="p-5">
            <LoadingRows rows={4} label="Loading incidents" />
          </div>
        ) : items.length === 0 ? (
          <div className="p-5">
            <EmptyState
              icon="alert"
              title="No incidents yet"
              description="Create one to start a structured investigation."
              action={
                <Button size="sm" icon="plus" onClick={() => setCreating(true)}>
                  New incident
                </Button>
              }
            />
          </div>
        ) : visible.length === 0 ? (
          <div className="p-5">
            <EmptyState icon="search" title="No matching incidents" description="Try a different search or severity." />
          </div>
        ) : (
          <>
            <table className="hidden w-full text-sm md:table">
              <thead className="border-b border-zinc-100 bg-zinc-50/60">
                <tr>
                  <th className={cx(th, "w-24")}>Severity</th>
                  <th className={th}>Incident</th>
                  <th className={th}>Status</th>
                  <th className={th}>Created</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {visible.map((i) => (
                  <tr key={i.id} className="cursor-pointer hover:bg-zinc-50/60" onClick={() => router.push(`/incidents/${i.id}`)}>
                    <td className={td}>
                      <Badge value={i.severity} />
                    </td>
                    <td className={td}>
                      <Link href={`/incidents/${i.id}`} className="font-medium text-zinc-900 hover:text-indigo-700" onClick={(e) => e.stopPropagation()}>
                        {i.title}
                      </Link>
                      <p className="text-xs text-zinc-500">
                        {i.service}
                        {i.environment && ` · ${i.environment}`}
                      </p>
                    </td>
                    <td className={td}>
                      <Badge value={i.status} />
                    </td>
                    <td className={cx(td, "whitespace-nowrap text-xs text-zinc-500")}>{new Date(i.created_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <ul className="divide-y divide-zinc-100 md:hidden">
              {visible.map((i) => (
                <li key={i.id}>
                  <Link href={`/incidents/${i.id}`} className="block space-y-1.5 p-4 hover:bg-zinc-50">
                    <div className="flex items-center gap-2">
                      <Badge value={i.severity} />
                      <Badge value={i.status} />
                    </div>
                    <p className="text-sm font-medium text-zinc-900">{i.title}</p>
                    <p className="text-xs text-zinc-500">
                      {i.service} · {new Date(i.created_at).toLocaleDateString()}
                    </p>
                  </Link>
                </li>
              ))}
            </ul>
          </>
        )}
      </Card>
      <Dialog
        open={creating}
        onClose={() => setCreating(false)}
        wide
        title="New incident"
        description="Credentials, tokens, emails and public IPs in the log excerpt are redacted before storage."
        footer={
          <>
            <Button variant="secondary" onClick={() => setCreating(false)}>
              Cancel
            </Button>
            <Button type="submit" form="new-incident" loading={busy}>
              {busy ? "Creating…" : "Create incident"}
            </Button>
          </>
        }
      >
        <form id="new-incident" className="space-y-5" onSubmit={create}>
          {formError && <ErrorBox message={formError} />}
          <fieldset className="grid gap-4 sm:grid-cols-2">
            <legend className="sr-only">Basics</legend>
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
          <Field label="Log excerpt" hint={`Optional · ${form.log_excerpt.length.toLocaleString()} / 20,000 characters · treated as untrusted data`}>
            {(p) => (
              <textarea {...p} className={`${input} font-mono text-xs`} rows={8} value={form.log_excerpt} onChange={set("log_excerpt")} maxLength={20000} />
            )}
          </Field>
        </form>
      </Dialog>
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
