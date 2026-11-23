"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState, type ReactNode } from "react";
import { Icon } from "@/components/icons";
import {
  AiLabel,
  Alert,
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorBox,
  Field,
  LoadingRows,
  PageHeader,
  Tabs,
  btn,
  cx,
  input,
  useToast,
} from "@/components/ui";
import { api, errorText, patch, post, type Analysis, type Hypothesis, type IncidentDetail, type Rca, type RcaBody, type Step } from "@/lib/api";

type Tab = "overview" | "analysis" | "rca";
type Run = (label: string, fn: () => Promise<unknown>, success?: string, then?: () => void) => Promise<void>;

export default function IncidentWorkspace() {
  const { id } = useParams<{ id: string }>();
  const toast = useToast();
  const [inc, setInc] = useState<IncidentDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [context, setContext] = useState("");
  const [tab, setTab] = useState<Tab | null>(null);

  const load = useCallback(() => {
    api<IncidentDetail>(`/incidents/${id}`)
      .then(setInc)
      .catch((e) => setError(errorText(e)));
  }, [id]);
  useEffect(load, [load]);

  const run: Run = async (label, fn, success, then) => {
    setBusy(label);
    setError(null);
    try {
      await fn();
      if (success) toast("success", success);
      then?.();
      load();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(null);
    }
  };

  if (!inc)
    return error ? (
      <ErrorBox message={error} />
    ) : (
      <div className="space-y-4">
        <LoadingRows rows={2} label="Loading incident" />
        <LoadingRows rows={6} />
      </div>
    );

  const a = inc.latest_analysis;
  const current: Tab = tab ?? (inc.rca ? "rca" : a ? "analysis" : "overview");

  return (
    <div>
      <PageHeader
        crumbs={
          <nav aria-label="Breadcrumb" className="flex items-center gap-1 text-xs text-zinc-500">
            <Link href="/incidents" className="hover:text-zinc-800">
              Incidents
            </Link>
            <Icon name="chevronRight" className="h-3 w-3" />
            <span className="truncate text-zinc-700" aria-current="page">
              {inc.title}
            </span>
          </nav>
        }
        title={inc.title}
        description={
          <span className="flex flex-wrap items-center gap-2">
            <Badge value={inc.severity} />
            <Badge value={inc.status} />
            {inc.rca && <Badge value={inc.rca.cause_status}>Cause {inc.rca.cause_status.toLowerCase()}</Badge>}
            <span className="text-zinc-500">
              {inc.service}
              {inc.environment && ` · ${inc.environment}`}
            </span>
          </span>
        }
      />
      <div className="space-y-5">
        <ErrorBox message={error} />
        <Tabs<Tab>
          label="Incident sections"
          value={current}
          onChange={setTab}
          tabs={[
            { id: "overview", label: "Overview" },
            { id: "analysis", label: "Analysis", count: a ? a.hypotheses.length : undefined },
            { id: "rca", label: "RCA" },
          ]}
        />
        <div role="tabpanel" id="panel-overview" aria-labelledby="tab-overview" hidden={current !== "overview"}>
          <OverviewTab inc={inc} onAnalyze={() => setTab("analysis")} />
        </div>
        <div role="tabpanel" id="panel-analysis" aria-labelledby="tab-analysis" hidden={current !== "analysis"}>
          <div className="space-y-5">
            <Card>
              <form
                className="flex flex-col gap-3 sm:flex-row sm:items-end"
                onSubmit={(e) => {
                  e.preventDefault();
                  run("analyze", () => post(`/incidents/${id}/analyze`, { context: context || null }), "Analysis complete.");
                }}
              >
                <Field label="Extra context" hint="Optional, e.g. a recent deploy. Treated as untrusted data." className="flex-1">
                  {(p) => <input {...p} className={input} placeholder="Deployed v2.3 at 09:05" value={context} onChange={(e) => setContext(e.target.value)} />}
                </Field>
                <Button type="submit" icon={a ? "refresh" : "sparkle"} loading={busy === "analyze"} disabled={!!busy} className="sm:mb-5">
                  {busy === "analyze" ? "Analyzing…" : a ? "Re-analyze" : "Analyze incident"}
                </Button>
              </form>
            </Card>
            {a ? (
              <AnalysisView a={a} />
            ) : (
              <EmptyState icon="sparkle" title="No analysis yet" description="Run an analysis to extract observations, suspected causes and read-only verification steps." />
            )}
          </div>
        </div>
        <div role="tabpanel" id="panel-rca" aria-labelledby="tab-rca" hidden={current !== "rca"}>
          <RcaEditor key={inc.rca?.updated_at ?? "none"} incidentId={id} rca={inc.rca} analysisId={a?.id ?? null} busy={busy} run={run} onNeedAnalysis={() => setTab("analysis")} />
        </div>
      </div>
    </div>
  );
}

function OverviewTab({ inc, onAnalyze }: { inc: IncidentDetail; onAnalyze: () => void }) {
  const fmt = (v: string | null) => (v ? new Date(v).toLocaleString() : "–");
  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
      <Card title="Incident record">
        <dl className="space-y-3 text-sm">
          {(
            [
              ["Service", inc.service],
              ["Environment", inc.environment ?? "–"],
              ["Started", fmt(inc.started_at)],
              ["Detected", fmt(inc.detected_at)],
            ] as const
          ).map(([k, v]) => (
            <div key={k} className="grid grid-cols-[110px_1fr] gap-2">
              <dt className="text-zinc-500">{k}</dt>
              <dd className="min-w-0 break-words text-zinc-900">{v}</dd>
            </div>
          ))}
          <div className="border-t border-zinc-100 pt-3">
            <dt className="mb-1 text-zinc-500">Symptoms</dt>
            <dd className="whitespace-pre-wrap leading-relaxed text-zinc-900">{inc.symptoms}</dd>
          </div>
        </dl>
        {!inc.latest_analysis && (
          <Button className="mt-5 w-full" icon="sparkle" onClick={onAnalyze}>
            Continue to analysis
          </Button>
        )}
      </Card>
      <Card title="Sanitized log" description="Stored after redaction; this is what the model sees.">
        {inc.sanitized_log ? (
          <div className="space-y-3">
            <pre className="max-h-96 overflow-auto rounded-control bg-zinc-950 p-3 font-mono text-xs leading-relaxed text-zinc-100">{inc.sanitized_log}</pre>
            {inc.redaction_summary && Object.keys(inc.redaction_summary).length > 0 && (
              <div className="flex flex-wrap items-center gap-1.5 text-xs text-zinc-500">
                <Icon name="shield" className="h-3.5 w-3.5 text-emerald-600" /> Redacted:
                {Object.entries(inc.redaction_summary).map(([k, v]) => (
                  <Badge key={k} value={k} tone="neutral" dot={false}>
                    {k} ×{v}
                  </Badge>
                ))}
              </div>
            )}
          </div>
        ) : (
          <EmptyState icon="terminal" title="No log excerpt provided" description="Analysis will list the missing information." />
        )}
      </Card>
    </div>
  );
}

function Section({ title, count, hint, children }: { title: string; count?: number; hint?: ReactNode; children: ReactNode }) {
  return (
    <section className="min-w-0 space-y-2.5">
      <h3 className="flex flex-wrap items-baseline gap-2 text-sm font-semibold text-zinc-900">
        {title}
        {count !== undefined && <span className="rounded-full bg-zinc-100 px-1.5 text-xs font-medium tabular-nums text-zinc-600">{count}</span>}
        {hint && <span className="text-xs font-normal text-zinc-500">{hint}</span>}
      </h3>
      {children}
    </section>
  );
}

function StepItem({ s }: { s: Step }) {
  return (
    <li className="space-y-1.5 rounded-control border border-zinc-200 bg-white p-3">
      <code className="block overflow-x-auto whitespace-pre rounded bg-zinc-950 px-2.5 py-1.5 font-mono text-xs text-zinc-100">{s.command_or_check}</code>
      <p className="text-xs text-zinc-600">
        <span className="font-medium text-zinc-700">Expected:</span> {s.expected_result}
      </p>
      <p className="text-xs text-zinc-600">
        <span className="font-medium text-zinc-700">Meaning:</span> {s.interpretation}
      </p>
    </li>
  );
}

function HypothesisCard({ h, steps }: { h: Hypothesis; steps: Step[] }) {
  return (
    <li className="space-y-3 rounded-card border border-amber-200 bg-amber-50/40 p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <p className="font-medium text-zinc-900">
          <span className="mr-2 font-mono text-xs text-zinc-500">{h.id}</span>
          {h.title}
        </p>
        <div className="flex gap-1.5">
          <Badge value={h.status} />
          <Badge value={h.confidence}>{h.confidence} confidence</Badge>
        </div>
      </div>
      <p className="text-sm leading-relaxed text-zinc-700">{h.explanation}</p>
      <p className="text-xs text-zinc-500">
        Supports: <span className="font-mono">{h.supporting_evidence.join(", ") || "–"}</span> · Contradicts:{" "}
        <span className="font-mono">{h.contradicting_evidence.join(", ") || "–"}</span>
      </p>
      {steps.length > 0 && (
        <div className="space-y-2">
          <p className="flex items-center gap-1.5 text-xs font-medium text-zinc-700">
            <Icon name="terminal" className="h-3.5 w-3.5" /> Read-only verification
          </p>
          <ol className="space-y-2">
            {steps.map((s) => (
              <StepItem key={s.id} s={s} />
            ))}
          </ol>
        </div>
      )}
    </li>
  );
}

function AnalysisView({ a }: { a: Analysis }) {
  const orphanSteps = a.verification_steps.filter((s) => !a.hypotheses.some((h) => h.id === s.hypothesis_id));
  return (
    <div className="space-y-5 text-sm">
      <Alert tone="warning">
        <span className="flex flex-wrap items-center gap-2">
          <AiLabel /> {a.disclaimer ?? "AI-generated suspected causes; nothing here is confirmed."}
          <span className="text-xs text-amber-700">
            {a.provider}/{a.model} · {new Date(a.created_at).toLocaleString()}
          </span>
        </span>
      </Alert>
      <div className="grid gap-6 xl:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <Section title="Observations" count={a.observations.length} hint="evidence from the log">
          {a.observations.length === 0 ? (
            <EmptyState title="No observations extracted" />
          ) : (
            <ul className="space-y-2">
              {a.observations.map((o) => (
                <li key={o.id} className="rounded-control border border-zinc-200 bg-white p-3">
                  <p className="flex flex-wrap items-center gap-x-2 text-xs text-zinc-500">
                    <span className="font-mono">{o.id}</span>
                    <span>
                      {o.source}
                      {o.line_number ? ` · line ${o.line_number}` : ""}
                    </span>
                    <span className="rounded bg-zinc-100 px-1.5 font-mono text-[11px] text-zinc-600">{o.category}</span>
                  </p>
                  <pre className="mt-1.5 whitespace-pre-wrap break-words font-mono text-xs text-zinc-800">{o.excerpt}</pre>
                  {o.interpretation && <p className="mt-1.5 text-xs text-zinc-600">{o.interpretation}</p>}
                </li>
              ))}
            </ul>
          )}
        </Section>
        <div className="min-w-0 space-y-6">
          <Section title="Hypotheses" count={a.hypotheses.length} hint="suspected, unconfirmed">
            <ul className="space-y-3">
              {a.hypotheses.map((h) => (
                <HypothesisCard key={h.id} h={h} steps={a.verification_steps.filter((s) => s.hypothesis_id === h.id)} />
              ))}
            </ul>
          </Section>
          {orphanSteps.length > 0 && (
            <Section title="Other verification steps" hint="never executed by ResolveAI">
              <ol className="space-y-2">
                {orphanSteps.map((s) => (
                  <StepItem key={s.id} s={s} />
                ))}
              </ol>
            </Section>
          )}
          <p className="flex items-center gap-1.5 text-xs text-zinc-500">
            <Icon name="shield" className="h-3.5 w-3.5" /> Verification steps are suggestions only and are never executed by ResolveAI.
          </p>
          {a.missing_information.length > 0 && (
            <Section title="Missing information" count={a.missing_information.length}>
              <ul className="list-disc space-y-1 pl-5 text-zinc-700">
                {a.missing_information.map((m, i) => (
                  <li key={i}>{m}</li>
                ))}
              </ul>
            </Section>
          )}
          {a.safety_warnings.length > 0 && (
            <Alert tone="danger" title="Safety warnings">
              <ul className="list-disc space-y-1 pl-5">
                {a.safety_warnings.map((w, i) => (
                  <li key={i}>
                    {w.command && <code className="font-mono text-xs">{w.command}</code>} {w.reason}
                  </li>
                ))}
              </ul>
            </Alert>
          )}
          {a.evidence.length > 0 && (
            <Section title="Knowledge base evidence" count={a.evidence.length}>
              <div className="flex flex-wrap gap-1.5">
                {a.evidence.map((e) => (
                  <span key={e.chunk_id} className="inline-flex items-center gap-1 rounded-full border border-zinc-200 bg-white px-2 py-0.5 text-xs text-zinc-700">
                    <Icon name="file" className="h-3 w-3 text-zinc-400" />
                    {e.filename ?? e.chunk_id}
                    {e.page_number ? ` p.${e.page_number}` : ""}
                  </span>
                ))}
              </div>
            </Section>
          )}
        </div>
      </div>
    </div>
  );
}

const lines = (xs: string[]) => xs.join("\n");
const unlines = (s: string) => s.split("\n").map((x) => x.trim()).filter(Boolean);
const timelineText = (items: RcaBody["timeline"]) => lines(items.map((t) => `${t.time ?? ""} | ${t.event} | ${t.source}`));
const parseTimeline = (value: string): RcaBody["timeline"] =>
  unlines(value).map((line) => {
    const [time, event = "", source = ""] = line.split("|").map((x) => x.trim());
    return { time: time || null, event, source };
  });
const evidenceText = (items: RcaBody["evidence_appendix"]) => lines(items.map((item) => `${item.ref} | ${item.excerpt}`));
const parseEvidence = (value: string): RcaBody["evidence_appendix"] =>
  unlines(value).map((line) => {
    const [ref, ...rest] = line.split("|");
    return { ref: ref.trim(), excerpt: rest.join("|").trim() };
  });
const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);

type TextKey = "incident_summary" | "customer_impact" | "detection" | "resolution" | "suspected_cause" | "confirmed_cause";

function RcaEditor({
  incidentId,
  rca,
  analysisId,
  busy,
  run,
  onNeedAnalysis,
}: {
  incidentId: string;
  rca: Rca | null;
  analysisId: string | null;
  busy: string | null;
  run: Run;
  onNeedAnalysis: () => void;
}) {
  const [body, setBody] = useState<RcaBody | null>(rca?.body_json ?? null);
  // Multi-line fields keep raw text while typing and are parsed only for comparison/saving.
  const [raw, setRaw] = useState(() => ({
    timeline: rca ? timelineText(rca.body_json.timeline) : "",
    evidence: rca ? evidenceText(rca.body_json.evidence_appendix) : "",
    corrective: rca ? lines(rca.body_json.corrective_actions) : "",
    preventive: rca ? lines(rca.body_json.preventive_actions) : "",
  }));
  const [ack, setAck] = useState(false);

  const generate = (variant: "primary" | "secondary") => (
    <Button
      variant={variant}
      icon="sparkle"
      disabled={!analysisId || !!busy}
      loading={busy === "rca"}
      onClick={() => run("rca", () => post(`/incidents/${incidentId}/rca`, { analysis_id: analysisId }), "RCA draft generated — cause remains UNCONFIRMED.")}
    >
      {busy === "rca" ? "Generating…" : rca ? "Regenerate draft" : "Generate RCA draft"}
    </Button>
  );
  if (!rca || !body) {
    return (
      <EmptyState
        icon="file"
        title="No RCA draft yet"
        description={analysisId ? "Generate a structured draft from the latest analysis. It stays unconfirmed until a reviewer signs off." : "RCA drafts are generated from an analysis. Run one first."}
        action={
          analysisId ? (
            generate("primary")
          ) : (
            <Button variant="secondary" icon="sparkle" onClick={onNeedAnalysis}>
              Go to analysis
            </Button>
          )
        }
      />
    );
  }

  const orig = rca.body_json;
  const parsed = {
    timeline: parseTimeline(raw.timeline),
    evidence: parseEvidence(raw.evidence),
    corrective: unlines(raw.corrective),
    preventive: unlines(raw.preventive),
  };
  const changed = {
    timeline: !same(parsed.timeline, parseTimeline(timelineText(orig.timeline))),
    evidence: !same(parsed.evidence, parseEvidence(evidenceText(orig.evidence_appendix))),
    corrective: !same(parsed.corrective, unlines(lines(orig.corrective_actions))),
    preventive: !same(parsed.preventive, unlines(lines(orig.preventive_actions))),
  };
  const textKeys: TextKey[] = ["incident_summary", "customer_impact", "detection", "resolution", "suspected_cause", "confirmed_cause"];
  const dirty = textKeys.some((k) => body[k] !== orig[k]) || Object.values(changed).some(Boolean);
  const confirmed = rca.cause_status === "CONFIRMED";
  const gates: [string, boolean][] = [
    ["Confirmed cause is filled in", body.confirmed_cause.trim() !== ""],
    ["Evidence appendix has at least one entry", parsed.evidence.length > 0],
    ["All changes are saved", !dirty],
    ["Reviewer acknowledgement checked", ack],
  ];
  const canConfirm = gates.every(([, ok]) => ok);

  const save = () =>
    run(
      "save",
      () =>
        patch(`/incidents/${incidentId}/rca`, {
          body_json: {
            ...body,
            timeline: changed.timeline ? parsed.timeline : orig.timeline,
            evidence_appendix: changed.evidence ? parsed.evidence : orig.evidence_appendix,
            corrective_actions: changed.corrective ? parsed.corrective : orig.corrective_actions,
            preventive_actions: changed.preventive ? parsed.preventive : orig.preventive_actions,
          },
        }),
      confirmed ? "Draft saved — review reset to UNCONFIRMED." : "Draft saved.",
    );

  const text = (k: TextKey, label: string, rows = 3, hint?: string) => (
    <Field label={label} hint={hint}>
      {(p) => <textarea {...p} className={input} rows={rows} value={body[k]} onChange={(e) => setBody({ ...body, [k]: e.target.value })} />}
    </Field>
  );
  const rawField = (k: keyof typeof raw, label: string, hint: string, mono = false) => (
    <Field label={label} hint={hint}>
      {(p) => <textarea {...p} className={cx(input, mono && "font-mono text-xs")} rows={4} value={raw[k]} onChange={(e) => setRaw({ ...raw, [k]: e.target.value })} />}
    </Field>
  );

  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_300px]">
      <div className="min-w-0 space-y-5">
        <Alert tone="info">
          <span className="flex flex-wrap items-center gap-2">
            <AiLabel /> Draft generated from analysis; edit freely. A cause is only CONFIRMED by explicit reviewer acknowledgement.
          </span>
        </Alert>
        <Card title="Summary">
          <div className="grid gap-4 md:grid-cols-2">
            {text("incident_summary", "Incident summary")}
            {text("customer_impact", "Customer impact", 3)}
            {text("detection", "Detection", 2)}
            {text("resolution", "Resolution", 2)}
          </div>
        </Card>
        <Card title="Timeline">{rawField("timeline", "Events", "One per line: time | event | source", true)}</Card>
        <Card title="Root cause" description="Keep the suspected cause separate from what a reviewer has verified.">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="rounded-card border border-amber-200 bg-amber-50/40 p-3">{text("suspected_cause", "Suspected cause (unconfirmed)", 4)}</div>
            <div className="rounded-card border border-emerald-200 bg-emerald-50/40 p-3">
              {text("confirmed_cause", "Confirmed cause", 4, "Reviewer fills this in after verifying evidence.")}
            </div>
          </div>
        </Card>
        <Card title="Actions">
          <div className="grid gap-4 md:grid-cols-2">
            {rawField("corrective", "Corrective actions", "One per line")}
            {rawField("preventive", "Preventive actions", "One per line")}
          </div>
        </Card>
        <Card title="Evidence appendix">{rawField("evidence", "Evidence", "One per line: ref | excerpt", true)}</Card>
      </div>
      <aside className="lg:sticky lg:top-8 lg:self-start">
        <Card title="Review" description={confirmed ? "This RCA has been confirmed by a reviewer." : "Root cause is not confirmed."}>
          <div className="space-y-4">
            <ol className="flex items-center gap-2 text-xs font-medium" aria-label="RCA status">
              <li className="flex items-center gap-1.5 text-zinc-900">
                <span className="grid h-5 w-5 place-items-center rounded-full bg-amber-100 text-amber-800">1</span>Draft
              </li>
              <span className="h-px flex-1 bg-zinc-200" aria-hidden="true" />
              <li className={cx("flex items-center gap-1.5", confirmed ? "text-zinc-900" : "text-zinc-500")} aria-current={confirmed ? "step" : undefined}>
                <span className={cx("grid h-5 w-5 place-items-center rounded-full", confirmed ? "bg-emerald-100 text-emerald-700" : "bg-zinc-100")}>
                  {confirmed ? <Icon name="check" className="h-3 w-3" /> : "2"}
                </span>
                Confirmed
              </li>
            </ol>
            <div className="flex flex-wrap gap-1.5">
              <Badge value={rca.status} />
              <Badge value={rca.cause_status}>Cause {rca.cause_status.toLowerCase()}</Badge>
            </div>
            {rca.reviewed_at && rca.reviewer_email && (
              <p className="text-xs text-zinc-600">
                Reviewed by <span className="font-medium">{rca.reviewer_email}</span> at {new Date(rca.reviewed_at).toLocaleString()}.
              </p>
            )}
            <div className="space-y-2 border-t border-zinc-100 pt-4">
              <Button className="w-full" variant={dirty ? "primary" : "secondary"} disabled={!dirty || !!busy} loading={busy === "save"} onClick={save}>
                {busy === "save" ? "Saving…" : "Save draft"}
              </Button>
              {dirty && (
                <p className="text-xs text-amber-700" role="status">
                  Unsaved changes{confirmed && " — saving resets the review to UNCONFIRMED"}
                </p>
              )}
              <a className={cx(btn("secondary"), "w-full")} href={`/api/v1/incidents/${incidentId}/rca/export`}>
                <Icon name="download" /> Export Markdown
              </a>
              <div className="[&>button]:w-full">{generate("secondary")}</div>
            </div>
            {!confirmed && (
              <div className="space-y-3 border-t border-zinc-100 pt-4">
                <p className="text-xs font-medium text-zinc-700">Before confirming</p>
                <ul className="space-y-1.5 text-xs">
                  {gates.map(([label, ok]) => (
                    <li key={label} className={cx("flex items-center gap-2", ok ? "text-zinc-700" : "text-zinc-500")}>
                      <span className={cx("grid h-4 w-4 place-items-center rounded-full", ok ? "bg-emerald-100 text-emerald-700" : "border border-zinc-300")}>
                        {ok && <Icon name="check" className="h-2.5 w-2.5" />}
                      </span>
                      {label}
                    </li>
                  ))}
                </ul>
                <label className="flex items-start gap-2 rounded-control border border-zinc-200 bg-zinc-50 p-3 text-xs text-zinc-700">
                  <input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} className="mt-0.5 h-4 w-4 accent-indigo-600" />
                  <span>I have reviewed the verification evidence and confirm the cause stated in “Confirmed cause”. This records me as reviewer with a timestamp.</span>
                </label>
                <Button
                  className="w-full"
                  icon="check"
                  disabled={!canConfirm || !!busy}
                  loading={busy === "confirm"}
                  onClick={() =>
                    run(
                      "confirm",
                      () => post(`/incidents/${incidentId}/rca/confirm`, { reviewer_acknowledgement: true, expected_updated_at: rca.updated_at }),
                      "Root cause confirmed.",
                    )
                  }
                >
                  Confirm root cause
                </Button>
              </div>
            )}
          </div>
        </Card>
      </aside>
    </div>
  );
}
