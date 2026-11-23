"use client";

import { useEffect, useState } from "react";
import { Alert, Button, Card, ErrorBox, Field, PageHeader, input } from "@/components/ui";
import { api, errorText, post, providerNames, type Me } from "@/lib/api";

const KEPT = [
  ["incidents", "Incidents, with their analyses and RCA reports"],
  ["conversations", "Assistant conversations"],
  ["logs", "Request and model usage records"],
  ["audit", "Audit log entries"],
] as const;

function DataSharing() {
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    api<Me>("/auth/me").then(setMe).catch((e) => setError(errorText(e)));
  }, []);
  const providers = providerNames(me?.external_llm_providers ?? []);
  const allowed = me && !me.llm_consent_required;
  const decide = async (granted: boolean) => {
    setBusy(true);
    setError(null);
    try {
      setMe(await api<Me>("/auth/llm-consent", { method: "PUT", body: JSON.stringify({ granted }) }));
    } catch (e) {
      setError(errorText(e));
    }
    setBusy(false);
  };

  return (
    <Card title="Data sent to the model provider" description="Your decision applies to this account only and is recorded in the audit log.">
      <div className="max-w-[65ch] space-y-4 text-sm">
        <ErrorBox message={error} />
        {me && !providers && <p>This workspace runs its models locally. Your documents, questions and incident logs stay on this server.</p>}
        {me && providers && (
          <>
            <p>
              This workspace uses {providers}. Asking the assistant, analyzing an incident, drafting an RCA and indexing a document send your question, the matching document excerpts, and the incident symptoms and
              redacted log to {providers}.
            </p>
            <p className="text-muted">
              {allowed
                ? `You allowed this on ${new Date(me.llm_consent_at ?? "").toLocaleString()}.`
                : "Until you allow it, those four actions are blocked. Everything else keeps working."}
            </p>
            <Button variant={allowed ? "secondary" : "primary"} loading={busy} onClick={() => decide(!allowed)}>
              {allowed ? "Withdraw permission" : `Allow sending to ${providers}`}
            </Button>
          </>
        )}
      </div>
    </Card>
  );
}

function Retention() {
  const [days, setDays] = useState<Record<string, number> | null>(null);
  useEffect(() => {
    api<{ retention_days: Record<string, number> }>("/auth/config")
      .then((c) => setDays(c.retention_days))
      .catch(() => undefined);
  }, []);
  if (!days) return null;
  return (
    <Card title="Data retention" description="Set by the administrator of this workspace. Documents stay until you delete them.">
      <dl className="max-w-[65ch] divide-y divide-rule text-sm">
        {KEPT.map(([key, label]) => (
          <div key={key} className="flex justify-between gap-6 py-2">
            <dt>{label}</dt>
            <dd className="measured whitespace-nowrap text-muted">{days[key] ? `deleted after ${days[key]} days` : "kept until deleted"}</dd>
          </div>
        ))}
      </dl>
    </Card>
  );
}

export default function AccountPage() {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  return (
    <div className="space-y-6">
      <PageHeader title="Account" description="Settings for the account you are signed in with." />
      <Card title="Change password" description="Changing it signs out every other session of this account.">
        <form
          className="max-w-sm space-y-5"
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError(null);
            setDone(false);
            try {
              await post("/auth/password", { current_password: current, new_password: next });
              setCurrent("");
              setNext("");
              setDone(true);
            } catch (err) {
              setError(errorText(err));
            }
            setBusy(false);
          }}
        >
          <ErrorBox message={error} />
          {done && <Alert tone="success">Password changed.</Alert>}
          <Field label="Current password">
            {(p) => <input {...p} className={input} type="password" value={current} onChange={(e) => setCurrent(e.target.value)} required autoComplete="current-password" />}
          </Field>
          <Field label="New password" hint="12 to 72 characters.">
            {(p) => (
              <input {...p} className={input} type="password" value={next} onChange={(e) => setNext(e.target.value)} required minLength={12} maxLength={72} autoComplete="new-password" />
            )}
          </Field>
          <Button type="submit" loading={busy}>
            Change password
          </Button>
        </form>
      </Card>
      <DataSharing />
      <Retention />
    </div>
  );
}
