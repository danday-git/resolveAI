"use client";

import { useEffect, useState } from "react";
import { Alert, Button, Card, ErrorBox, Field, LoadingRows, PageHeader, cx, input } from "@/components/ui";
import { api, errorText, post, providerNames, type AiSettings } from "@/lib/api";

const PROVIDERS = [
  ["ollama", "Ollama (local, free)", "llama3.2:3b"],
  ["openai", "OpenAI", "gpt-4o-mini"],
  ["anthropic", "Anthropic", "claude-haiku-4-5"],
  ["mock", "Mock (no model, for tests)", "mock-extractive-v1"],
] as const;
type Provider = (typeof PROVIDERS)[number][0];
const KEY_FIELD = { openai: "openai_api_key", anthropic: "anthropic_api_key" } as const;

function KeyStatus({ state }: { state: AiSettings["openai_api_key"] }) {
  if (!state.set) return <>No key saved.</>;
  return (
    <>
      Saved key ends in <span className="measured text-ink">{state.last4}</span>
      {state.source === "env" ? " (from the server environment)." : ". It is stored encrypted and never shown again."}
    </>
  );
}

export default function AiProviderPage() {
  const [data, setData] = useState<AiSettings | null>(null);
  const [provider, setProvider] = useState<Provider>("ollama");
  const [model, setModel] = useState("");
  const [key, setKey] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState<"save" | "test" | "remove" | null>(null);

  const show = (d: AiSettings) => {
    setData(d);
    setProvider(d.llm_provider);
    setModel(d.llm_model);
    setKey("");
  };
  useEffect(() => {
    api<AiSettings>("/admin/ai").then(show).catch((e) => setError(errorText(e)));
  }, []);

  const keyField = provider === "openai" || provider === "anthropic" ? KEY_FIELD[provider] : null;
  const run = async (kind: "save" | "test" | "remove", body?: Record<string, string>) => {
    setBusy(kind);
    setError(null);
    setNotice(null);
    try {
      if (kind === "test") {
        const r = await post<{ ok: boolean; provider: string; model?: string; latency_ms?: number; error?: string }>("/admin/ai/test");
        setNotice(r.ok ? `Connected to ${r.provider} ${r.model} in ${r.latency_ms} ms.` : `The provider did not answer (${r.error}). Check the model name and key.`);
      } else {
        show(await api<AiSettings>("/admin/ai", { method: "PUT", body: JSON.stringify({ llm_provider: provider, llm_model: model, ...body }) }));
        setNotice(kind === "remove" ? "Key removed." : "Saved. New questions and analyses use this model.");
      }
    } catch (e) {
      setError(errorText(e));
    }
    setBusy(null);
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="AI provider"
        description="Choose the model that answers questions, analyzes incidents and drafts RCAs for every account. Only administrators see this page."
      />
      <ErrorBox message={error} />
      {notice && <Alert tone="info">{notice}</Alert>}
      {!data ? (
        error ? null : <LoadingRows label="Loading settings" />
      ) : (
        <>
          <Card title="Chat model" description={data.source === "admin" ? `Last changed by ${data.updated_by} on ${new Date(data.updated_at ?? "").toLocaleString()}.` : "Using the server environment settings until you save here."}>
            <form
              className="max-w-xl space-y-5"
              onSubmit={(e) => {
                e.preventDefault();
                run("save", keyField && key.trim() ? { [keyField]: key.trim() } : undefined);
              }}
            >
              <Field label="Provider">
                {(p) => (
                  <select
                    {...p}
                    className={input}
                    value={provider}
                    onChange={(e) => {
                      const next = e.target.value as Provider;
                      setProvider(next);
                      setModel(next === data.llm_provider ? data.llm_model : PROVIDERS.find((x) => x[0] === next)![2]);
                      setKey("");
                    }}
                  >
                    {PROVIDERS.map(([id, name]) => (
                      <option key={id} value={id}>
                        {name}
                      </option>
                    ))}
                  </select>
                )}
              </Field>
              <Field label="Model" hint={provider === "ollama" ? "The model must already be pulled on the Ollama server, for example llama3.2:3b." : undefined}>
                {(p) => <input {...p} className={cx(input, "measured")} value={model} onChange={(e) => setModel(e.target.value)} required maxLength={100} />}
              </Field>
              {keyField && (
                <Field label={`${providerNames([provider])} API key`} hint={<KeyStatus state={data[keyField]} />}>
                  {(p) => (
                    <input
                      {...p}
                      type="password"
                      autoComplete="off"
                      className={cx(input, "measured")}
                      placeholder={data[keyField].set ? "Leave empty to keep the saved key" : "Paste the key"}
                      value={key}
                      onChange={(e) => setKey(e.target.value)}
                      maxLength={500}
                    />
                  )}
                </Field>
              )}
              {keyField && (
                <Alert tone="warning">
                  {providerNames([provider])} is an external service. After you save, every user must allow sending their data to it on the Account page before they can use the assistant again.
                </Alert>
              )}
              <div className="flex flex-wrap gap-2">
                <Button type="submit" icon="check" loading={busy === "save"}>
                  Save
                </Button>
                <Button variant="secondary" icon="refresh" loading={busy === "test"} onClick={() => run("test")}>
                  Test connection
                </Button>
                {keyField && data[keyField].source === "admin" && (
                  <Button variant="secondary" icon="trash" loading={busy === "remove"} onClick={() => run("remove", { [keyField]: "" })}>
                    Remove saved key
                  </Button>
                )}
              </div>
              <p className="text-xs text-muted">Test connection checks the saved settings, so save first.</p>
            </form>
          </Card>
          <Card title="Embedding model" description="Turns documents and questions into vectors for search. Set on the server, not here.">
            <p className="measured text-sm text-ink">
              {data.embedding.provider} / {data.embedding.model} ({data.embedding.dim} dimensions)
            </p>
            <p className="mt-2 text-sm text-muted">Changing it means a fresh database and uploading every document again, because vectors from different models cannot be compared.</p>
          </Card>
        </>
      )}
    </div>
  );
}
