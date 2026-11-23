"use client";

import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AiLabel, Badge, Card, Empty, ErrorBox, button, buttonSecondary, input } from "@/components/ui";
import { api, errorText, patch, post, type Analysis, type IncidentDetail, type Rca, type RcaBody } from "@/lib/api";

export default function IncidentWorkspace() {
  const { id } = useParams<{ id: string }>();
  const [inc, setInc] = useState<IncidentDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [context, setContext] = useState("");

  const load = useCallback(() => {
    api<IncidentDetail>(`/incidents/${id}`).then(setInc).catch((e) => setError(errorText(e)));
  }, [id]);
  useEffect(load, [load]);

  async function run(label: string, fn: () => Promise<unknown>) {
    setBusy(label);
    setError(null);
    try {
      await fn();
      load();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(null);
    }
  }

  if (!inc) return error ? <ErrorBox message={error} /> : <p className="text-sm text-slate-500">Loading…</p>;
  const a = inc.latest_analysis;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="text-2xl font-bold">{inc.title}</h1>
        <Badge value={inc.severity} />
        <Badge value={inc.status} />
      </div>
      <ErrorBox message={error} />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Incident record">
          <dl className="grid grid-cols-[120px_1fr] gap-1 text-sm">
            <dt className="text-slate-500">Service</dt><dd>{inc.service}</dd>
            <dt className="text-slate-500">Environment</dt><dd>{inc.environment ?? "–"}</dd>
            <dt className="text-slate-500">Started</dt><dd>{inc.started_at ?? "–"}</dd>
            <dt className="text-slate-500">Detected</dt><dd>{inc.detected_at ?? "–"}</dd>
            <dt className="text-slate-500">Symptoms</dt><dd className="whitespace-pre-wrap">{inc.symptoms}</dd>
          </dl>
        </Card>
        <Card title="Sanitized log">
          {inc.sanitized_log ? (
            <>
              <pre className="max-h-64 overflow-auto rounded bg-slate-900 p-3 text-xs text-slate-100">{inc.sanitized_log}</pre>
              {inc.redaction_summary && Object.keys(inc.redaction_summary).length > 0 && (
                <p className="mt-2 text-xs text-slate-500">
                  Redacted: {Object.entries(inc.redaction_summary).map(([k, v]) => `${k} ×${v}`).join(", ")}
                </p>
              )}
            </>
          ) : (
            <Empty>No log excerpt provided — analysis will list missing information.</Empty>
          )}
        </Card>
      </div>
      <Card
        title="Analysis"
        actions={
          <div className="flex items-center gap-2">
            <input className={`${input} w-64`} placeholder="Optional extra context" value={context} onChange={(e) => setContext(e.target.value)} />
            <button className={button} disabled={!!busy} onClick={() => run("analyze", () => post(`/incidents/${id}/analyze`, { context: context || null }))}>
              {busy === "analyze" ? "Analyzing…" : a ? "Re-analyze" : "Analyze"}
            </button>
          </div>
        }
      >
        {a ? <AnalysisView a={a} /> : <Empty>No analysis yet.</Empty>}
      </Card>
      <RcaEditor
        key={inc.rca?.updated_at ?? "none"}
        incidentId={id}
        rca={inc.rca}
        analysisId={a?.id ?? null}
        busy={busy}
        run={run}
      />
    </div>
  );
}

function AnalysisView({ a }: { a: Analysis }) {
  return (
    <div className="space-y-4 text-sm">
      <p className="flex items-center gap-2 text-xs text-slate-500">
        <AiLabel /> {a.disclaimer ?? "AI-generated suspected causes; nothing here is confirmed."} · {a.provider}/{a.model}
      </p>
      <section>
        <h3 className="mb-1 font-semibold">Observations (evidence)</h3>
        <ul className="space-y-1">
          {a.observations.map((o) => (
            <li key={o.id} className="rounded border border-slate-200 p-2">
              <span className="mr-2 font-mono text-xs text-slate-500">{o.id}</span>
              <span className="text-xs text-slate-500">{o.source}{o.line_number ? ` line ${o.line_number}` : ""} · {o.category}</span>
              <pre className="mt-1 whitespace-pre-wrap font-mono text-xs">{o.excerpt}</pre>
              {o.interpretation && <p className="mt-1 text-xs text-slate-600">{o.interpretation}</p>}
            </li>
          ))}
          {a.observations.length === 0 && <Empty>No observations extracted.</Empty>}
        </ul>
      </section>
      <section>
        <h3 className="mb-1 font-semibold">Hypotheses (suspected, unconfirmed)</h3>
        <ul className="space-y-2">
          {a.hypotheses.map((h) => (
            <li key={h.id} className="rounded border border-amber-200 bg-amber-50 p-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{h.title}</span>
                <Badge value={h.status} />
                <span className="text-xs">confidence: <Badge value={h.confidence} /></span>
              </div>
              <p className="mt-1">{h.explanation}</p>
              <p className="mt-1 text-xs text-slate-600">
                Supports: {h.supporting_evidence.join(", ") || "–"} · Contradicts: {h.contradicting_evidence.join(", ") || "–"}
              </p>
            </li>
          ))}
        </ul>
      </section>
      <section>
        <h3 className="mb-1 font-semibold">Read-only verification steps <span className="text-xs font-normal text-slate-500">(never executed by ResolveAI)</span></h3>
        <ol className="list-decimal space-y-2 pl-5">
          {a.verification_steps.map((s) => (
            <li key={s.id}>
              <code className="rounded bg-slate-100 px-1 font-mono text-xs">{s.command_or_check}</code>
              {s.hypothesis_id && <span className="ml-2 text-xs text-slate-500">for {s.hypothesis_id}</span>}
              <p className="text-xs text-slate-600">Expected: {s.expected_result}</p>
              <p className="text-xs text-slate-600">Meaning: {s.interpretation}</p>
            </li>
          ))}
        </ol>
      </section>
      {a.missing_information.length > 0 && (
        <section>
          <h3 className="mb-1 font-semibold">Missing information</h3>
          <ul className="list-disc pl-5">{a.missing_information.map((m, i) => <li key={i}>{m}</li>)}</ul>
        </section>
      )}
      {a.safety_warnings.length > 0 && (
        <section className="rounded border border-red-200 bg-red-50 p-2">
          <h3 className="mb-1 font-semibold text-red-800">Safety warnings</h3>
          <ul className="list-disc pl-5 text-red-800">
            {a.safety_warnings.map((w, i) => (
              <li key={i}>{w.command && <code className="font-mono text-xs">{w.command}</code>} {w.reason}</li>
            ))}
          </ul>
        </section>
      )}
      {a.evidence.length > 0 && (
        <p className="text-xs text-slate-500">
          KB evidence: {a.evidence.map((e) => `${e.filename ?? e.chunk_id}${e.page_number ? ` p.${e.page_number}` : ""}`).join(", ")}
        </p>
      )}
    </div>
  );
}

const lines = (xs: string[]) => xs.join("\n");
const unlines = (s: string) => s.split("\n").map((x) => x.trim()).filter(Boolean);

function RcaEditor({
  incidentId,
  rca,
  analysisId,
  busy,
  run,
}: {
  incidentId: string;
  rca: Rca | null;
  analysisId: string | null;
  busy: string | null;
  run: (label: string, fn: () => Promise<unknown>) => Promise<void>;
}) {
  const [body, setBody] = useState<RcaBody | null>(rca?.body_json ?? null);
  const [ack, setAck] = useState(false);

  const generate = (
    <button className={button} disabled={!analysisId || !!busy} onClick={() => run("rca", () => post(`/incidents/${incidentId}/rca`, { analysis_id: analysisId }))}>
      {busy === "rca" ? "Generating…" : rca ? "Regenerate draft" : "Generate RCA draft"}
    </button>
  );
  if (!rca || !body) {
    return (
      <Card title="RCA" actions={generate}>
        <Empty>{analysisId ? "No RCA draft yet." : "Run an analysis first; RCA drafts are generated from an analysis."}</Empty>
      </Card>
    );
  }

  const text = (k: keyof RcaBody, label: string, rows = 3) => (
    <label className="block text-sm">
      {label}
      <textarea className={input} rows={rows} value={body[k] as string} onChange={(e) => setBody({ ...body, [k]: e.target.value })} />
    </label>
  );
  const list = (k: "corrective_actions" | "preventive_actions", label: string) => (
    <label className="block text-sm">
      {label} <span className="text-xs text-slate-500">(one per line)</span>
      <textarea className={input} rows={3} value={lines(body[k])} onChange={(e) => setBody({ ...body, [k]: unlines(e.target.value) })} />
    </label>
  );
  const dirty = JSON.stringify(body) !== JSON.stringify(rca.body_json);
  const canConfirm = ack && !dirty && body.confirmed_cause.trim() !== "" && body.evidence_appendix.length > 0;

  return (
    <Card
      title="RCA editor"
      actions={
        <div className="flex flex-wrap items-center gap-2">
          <Badge value={rca.status} />
          <span className="text-xs">cause:</span>
          <Badge value={rca.cause_status} />
          {generate}
        </div>
      }
    >
      <div className="space-y-3">
        <p className="flex items-center gap-2 text-xs text-slate-500">
          <AiLabel /> Draft generated from analysis; edit freely. A cause is only CONFIRMED by explicit reviewer acknowledgement below.
          {rca.reviewed_at && ` Reviewed ${new Date(rca.reviewed_at).toLocaleString()}.`}
        </p>
        {text("incident_summary", "Incident summary")}
        {text("customer_impact", "Customer impact", 2)}
        <label className="block text-sm">
          Timeline <span className="text-xs text-slate-500">(one per line: time | event | source)</span>
          <textarea
            className={`${input} font-mono text-xs`}
            rows={4}
            value={lines(body.timeline.map((t) => `${t.time ?? ""} | ${t.event} | ${t.source}`))}
            onChange={(e) =>
              setBody({
                ...body,
                timeline: unlines(e.target.value).map((l) => {
                  const [time, event = "", source = ""] = l.split("|").map((x) => x.trim());
                  return { time: time || null, event, source };
                }),
              })
            }
          />
        </label>
        {text("detection", "Detection", 2)}
        {text("resolution", "Resolution", 2)}
        {text("suspected_cause", "Suspected cause (unconfirmed)")}
        {text("confirmed_cause", "Confirmed cause (reviewer fills this in after verifying evidence)", 2)}
        {list("corrective_actions", "Corrective actions")}
        {list("preventive_actions", "Preventive actions")}
        <label className="block text-sm">
          Evidence appendix <span className="text-xs text-slate-500">(one per line: ref | excerpt)</span>
          <textarea
            className={`${input} font-mono text-xs`}
            rows={4}
            value={lines(body.evidence_appendix.map((x) => `${x.ref} | ${x.excerpt}`))}
            onChange={(e) =>
              setBody({
                ...body,
                evidence_appendix: unlines(e.target.value).map((l) => {
                  const [ref, ...rest] = l.split("|");
                  return { ref: ref.trim(), excerpt: rest.join("|").trim() };
                }),
              })
            }
          />
        </label>
        <div className="flex flex-wrap items-center gap-2">
          <button className={button} disabled={!dirty || !!busy} onClick={() => run("save", () => patch(`/incidents/${incidentId}/rca`, { body_json: body }))}>
            {busy === "save" ? "Saving…" : "Save draft"}
          </button>
          {dirty && <span className="text-xs text-amber-700">Unsaved changes{rca.cause_status === "CONFIRMED" && " — saving resets the review to UNCONFIRMED"}</span>}
          <a className={buttonSecondary} href={`/api/v1/incidents/${incidentId}/rca/export`}>Export Markdown</a>
        </div>
        <div className="rounded border border-slate-200 bg-slate-50 p-3 text-sm">
          <label className="flex items-start gap-2">
            <input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} className="mt-1" />
            <span>I have reviewed the verification evidence and confirm the cause stated in “Confirmed cause”. This records me as reviewer with a timestamp.</span>
          </label>
          <button
            className={`${button} mt-2`}
            disabled={!canConfirm || !!busy || rca.cause_status === "CONFIRMED"}
            onClick={() => run("confirm", () => post(`/incidents/${incidentId}/rca/confirm`, { reviewer_acknowledgement: true }))}
          >
            Confirm root cause
          </button>
          {!body.confirmed_cause.trim() && <p className="mt-1 text-xs text-slate-500">Fill in “Confirmed cause” and save before confirming.</p>}
        </div>
      </div>
    </Card>
  );
}
