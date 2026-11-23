"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Badge, Card, Empty, ErrorBox, button, input } from "@/components/ui";
import { api, errorText, post, type Incident, type Page } from "@/lib/api";

const empty = { title: "", severity: "SEV3", service: "", symptoms: "", environment: "", started_at: "", detected_at: "", log_excerpt: "" };

export default function Incidents() {
  const router = useRouter();
  const [items, setItems] = useState<Incident[] | null>(null);
  const [form, setForm] = useState(empty);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

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
    setError(null);
    try {
      const body = Object.fromEntries(Object.entries(form).map(([k, v]) => [k, v === "" ? null : v]));
      if (body.started_at) body.started_at = new Date(body.started_at as string).toISOString();
      if (body.detected_at) body.detected_at = new Date(body.detected_at as string).toISOString();
      const inc = await post<Incident>("/incidents", body);
      router.push(`/incidents/${inc.id}`);
    } catch (err) {
      setError(errorText(err));
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <div className="space-y-4">
        <h1 className="text-2xl font-bold">Incidents</h1>
        <ErrorBox message={error} />
        <Card title="Open incidents">
          {items === null ? (
            <p className="text-sm text-slate-500">Loading…</p>
          ) : items.length === 0 ? (
            <Empty>No incidents yet.</Empty>
          ) : (
            <ul className="divide-y divide-slate-100 text-sm">
              {items.map((i) => (
                <li key={i.id} className="flex items-center gap-2 py-2">
                  <Badge value={i.severity} />
                  <Link className="flex-1 truncate hover:underline" href={`/incidents/${i.id}`}>{i.title}</Link>
                  <Badge value={i.status} />
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
      <Card title="New incident">
        <form className="space-y-3 text-sm" onSubmit={create}>
          <label className="block">Title<input className={input} value={form.title} onChange={set("title")} required maxLength={200} /></label>
          <div className="grid grid-cols-2 gap-3">
            <label className="block">Severity
              <select className={input} value={form.severity} onChange={set("severity")}>
                {["SEV1", "SEV2", "SEV3", "SEV4"].map((s) => <option key={s}>{s}</option>)}
              </select>
            </label>
            <label className="block">Service<input className={input} value={form.service} onChange={set("service")} required /></label>
            <label className="block">Started at<input className={input} type="datetime-local" value={form.started_at} onChange={set("started_at")} /></label>
            <label className="block">Detected at<input className={input} type="datetime-local" value={form.detected_at} onChange={set("detected_at")} /></label>
          </div>
          <label className="block">Environment<input className={input} value={form.environment} onChange={set("environment")} /></label>
          <label className="block">Symptoms<textarea className={input} rows={3} value={form.symptoms} onChange={set("symptoms")} required /></label>
          <label className="block">
            Log excerpt <span className="text-xs text-slate-500">(credentials, tokens, emails and public IPs are redacted before storage)</span>
            <textarea className={`${input} font-mono text-xs`} rows={8} value={form.log_excerpt} onChange={set("log_excerpt")} maxLength={20000} />
          </label>
          <button className={button} disabled={busy}>{busy ? "Creating…" : "Create incident"}</button>
        </form>
      </Card>
    </div>
  );
}
