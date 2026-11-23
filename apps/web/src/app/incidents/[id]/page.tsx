"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState, type ReactNode } from "react";
import { Icon } from "@/components/icons";
import { AiLabel, Alert, Badge, Button, Card, EmptyState, ErrorBox, Field, LoadingRows, PageHeader, Tabs, btn, cx, input, link } from "@/components/ui";
import { api, errorText, patch, post, type Analysis, type Hypothesis, type IncidentDetail, type Rca, type RcaBody, type Step } from "@/lib/api";
import { useQueryState } from "@/lib/url";

type Tab = "overview" | "analysis" | "rca";
type Run = (label: string, fn: () => Promise<unknown>) => Promise<void>;

function IncidentWorkspace() {
  const { id } = useParams<{ id: string }>();
  const [inc, setInc] = useState<IncidentDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [context, setContext] = useState("");
  const [tab, setTab] = useQueryState("tab");

  const load = useCallback(() => {
    api<IncidentDetail>(`/incidents/${id}`)
      .then(setInc)
      .catch((e) => setError(errorText(e)));
  }, [id]);
  useEffect(load, [load]);

  // No success toast: every action here changes something the reviewer already sees on the page.
  const run: Run = async (label, fn) => {
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
  const current: Tab = tab === "overview" || tab === "analysis" || tab === "rca" ? tab : inc.rca ? "rca" : a ? "analysis" : "overview";

  return (
    <div>
      <PageHeader
        crumbs={
          <nav aria-label="Breadcrumb" className="text-sm text-muted">
            <Link href="/incidents" className={cx(link, "inline-flex items-center gap-1")}>
              <Icon name="chevronLeft" className="h-3.5 w-3.5" />
              Incidents
            </Link>
          </nav>
        }
        title={inc.title}
        description={
          <span className="flex flex-wrap items-center gap-x-3 gap-y-2 text-sm">
            <Badge value={inc.severity} />
            <Badge value={inc.status} />
            {inc.rca && <Badge value={inc.rca.cause_status}>Cause {inc.rca.cause_status.toLowerCase()}</Badge>}
            <span>{inc.service}</span>
            {inc.environment && <span className="text-muted">{inc.environment}</span>}
          </span>
        }
      />
      <div className="space-y-6">
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
          <div className="space-y-6">
            <form
              className="flex max-w-3xl flex-col gap-3 sm:flex-row sm:items-end"
              onSubmit={(e) => {
                e.preventDefault();
                run("analyze", () => post(`/incidents/${id}/analyze`, { context: context || null }));
              }}
            >
              <Field label="Extra context" hint="Optional, e.g. a recent deploy. Treated as untrusted data." className="flex-1">
                {(p) => <input {...p} className={input} placeholder="Deployed v2.3 at 09:05" value={context} onChange={(e) => setContext(e.target.value)} />}
              </Field>
              <Button type="submit" variant={a ? "secondary" : "primary"} loading={busy === "analyze"} disabled={!!busy} icon={a ? "refresh" : "sparkle"} className="sm:mb-[1.375rem]">
                {busy === "analyze" ? "Analyzing…" : a ? "Re-analyze" : "Analyze incident"}
              </Button>
            </form>
            {a ? (
              <AnalysisView a={a} confirmed={inc.rca?.cause_status === "CONFIRMED"} onReview={() => setTab("rca")} />
            ) : (
              <EmptyState title="No analysis yet" description="An analysis reads the sanitized log and lists observations, suspected causes and read-only verification steps. Run one above." />
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

export default function IncidentWorkspacePage() {
  return (
    <Suspense>
      <IncidentWorkspace />
    </Suspense>
  );
}

function OverviewTab({ inc, onAnalyze }: { inc: IncidentDetail; onAnalyze: () => void }) {
  const fmt = (v: string | null) => (v ? new Date(v).toLocaleString() : "–");
  return (
    <div className="panels lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
      <section className="p-5">
        <h2>Incident record</h2>
        <dl className="mt-4 text-sm">
          {(
            [
              ["Service", inc.service, false],
              ["Environment", inc.environment ?? "–", false],
              ["Started", fmt(inc.started_at), true],
              ["Detected", fmt(inc.detected_at), true],
            ] as const
          ).map(([k, v, measured]) => (
            <div key={k} className="grid grid-cols-[7rem_minmax(0,1fr)] gap-2 border-t border-rule py-2">
              <dt className="text-muted">{k}</dt>
              <dd className={cx("break-words", measured && "measured")}>{v}</dd>
            </div>
          ))}
          <div className="border-t border-rule pt-3">
            <dt className="text-muted">Symptoms</dt>
            <dd className="mt-1 whitespace-pre-wrap text-ink-2">{inc.symptoms}</dd>
          </div>
        </dl>
        {!inc.latest_analysis && (
          <Button className="mt-5" onClick={onAnalyze}>
            Continue to analysis
            <Icon name="chevronRight" />
          </Button>
        )}
      </section>
      <section className="p-5">
        <h2>Sanitized log</h2>
        <p className="mt-1.5 text-sm text-muted">Stored after redaction. This is what the model sees.</p>
        {inc.sanitized_log ? (
          <>
            <pre className="measured mt-4 max-h-96 overflow-auto rounded-pill border border-rule bg-paper-3 p-3 text-ink-2">{inc.sanitized_log}</pre>
            {inc.redaction_summary && Object.keys(inc.redaction_summary).length > 0 && (
              <p className="mt-3 flex flex-wrap items-center gap-2 text-sm text-muted">
                Redacted
                {Object.entries(inc.redaction_summary).map(([k, v]) => (
                  <Badge key={k} value={k} tone="neutral">
                    {k} ×{v}
                  </Badge>
                ))}
              </p>
            )}
          </>
        ) : (
          <p className="mt-4 text-sm text-muted">No log excerpt was provided. The analysis will list it as missing information.</p>
        )}
      </section>
    </div>
  );
}

/** One entry on the evidence trail: a hairline tick on the spine, then the entry. */
function Entry({ children, person }: { children: ReactNode; person?: boolean }) {
  return (
    <li className="relative pb-8 pl-6 last:pb-0">
      <span className={cx("absolute left-0 top-3 h-px w-4", person ? "bg-accent" : "bg-rule-2")} aria-hidden="true" />
      {children}
    </li>
  );
}

function Stage({ title, count, hint }: { title: string; count?: number; hint?: string }) {
  return (
    <li className="relative pb-4 pl-6">
      <h3 className="flex flex-wrap items-baseline gap-x-3">
        {title}
        {count !== undefined && <span className="measured text-muted">{count}</span>}
        {hint && <span className="text-sm font-normal tracking-normal text-muted">{hint}</span>}
      </h3>
    </li>
  );
}

function StepItem({ s }: { s: Step }) {
  return (
    <li className="space-y-2">
      <code className="measured block overflow-x-auto whitespace-pre rounded-pill border border-rule bg-paper-3 px-3 py-2 text-ink">{s.command_or_check}</code>
      <dl className="grid grid-cols-[5rem_minmax(0,1fr)] gap-x-3 gap-y-1 text-sm">
        <dt className="text-muted">Expected</dt>
        <dd className="text-ink-2">{s.expected_result}</dd>
        <dt className="text-muted">Meaning</dt>
        <dd className="text-ink-2">{s.interpretation}</dd>
      </dl>
    </li>
  );
}

function HypothesisEntry({ h, steps }: { h: Hypothesis; steps: Step[] }) {
  return (
    <Entry>
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="measured text-cool">{h.id}</span>
        <p className="text-ink">{h.title}</p>
        <Badge value={h.status} />
        <Badge value={h.confidence} tone="neutral">
          {h.confidence} confidence
        </Badge>
      </div>
      <p className="mt-2 max-w-[75ch] text-sm text-ink-2">{h.explanation}</p>
      <dl className="mt-2 grid grid-cols-[5rem_minmax(0,1fr)] gap-x-3 gap-y-1 text-sm">
        <dt className="text-muted">Supports</dt>
        <dd className="measured text-cool">{h.supporting_evidence.join(", ") || "–"}</dd>
        <dt className="text-muted">Contradicts</dt>
        <dd className="measured text-cool">{h.contradicting_evidence.join(", ") || "–"}</dd>
      </dl>
      {steps.length > 0 && (
        <div className="mt-4 max-w-[75ch]">
          <p className="text-sm text-muted">Checks to run yourself (read-only; ResolveAI never runs them)</p>
          <ol className="mt-2 space-y-4">
            {steps.map((s) => (
              <StepItem key={s.id} s={s} />
            ))}
          </ol>
        </div>
      )}
    </Entry>
  );
}

/** The evidence trail: what the log shows, what the model suspects, how to check it, and the reviewer's decision, on one spine. */
function AnalysisView({ a, confirmed, onReview }: { a: Analysis; confirmed: boolean; onReview: () => void }) {
  const orphanSteps = a.verification_steps.filter((s) => !a.hypotheses.some((h) => h.id === s.hypothesis_id));
  return (
    <div className="space-y-6">
      <Alert tone="info">
        <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <AiLabel />
          <span>{a.disclaimer ?? "AI-generated suspected causes; nothing here is confirmed."}</span>
          <span className="measured text-cool">
            {a.provider}/{a.model}
          </span>
          <span className="measured text-muted">{new Date(a.created_at).toLocaleString()}</span>
        </span>
      </Alert>
      <ol className="border-l border-rule-2" aria-label="Evidence trail">
        <Stage title="Observations" count={a.observations.length} hint="evidence from the log" />
        {a.observations.length === 0 && (
          <Entry>
            <p className="text-sm text-muted">No observations were extracted from the log.</p>
          </Entry>
        )}
        {a.observations.map((o) => (
          <Entry key={o.id}>
            <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <span className="measured text-cool">{o.id}</span>
              <span className="measured text-muted">
                {o.source}
                {o.line_number ? `, line ${o.line_number}` : ""}
              </span>
              <span className="measured min-w-0 break-words text-muted">{o.category}</span>
            </div>
            <pre className="measured mt-2 max-w-[90ch] whitespace-pre-wrap break-words rounded-pill border border-rule bg-paper-3 px-3 py-2 text-ink">{o.excerpt}</pre>
            {o.interpretation && <p className="mt-2 max-w-[75ch] text-sm text-ink-2">{o.interpretation}</p>}
          </Entry>
        ))}
        {a.evidence.length > 0 && (
          <>
            <Stage title="Knowledge base evidence" count={a.evidence.length} />
            <Entry>
              <ul className="measured space-y-1 text-ink-2">
                {a.evidence.map((e) => (
                  <li key={e.chunk_id}>
                    {e.filename ?? e.chunk_id}
                    {e.page_number ? `, page ${e.page_number}` : ""}
                  </li>
                ))}
              </ul>
            </Entry>
          </>
        )}
        <Stage title="Possible causes" count={a.hypotheses.length} hint="suspected, not confirmed; verify with the checks below" />
        {a.hypotheses.map((h) => (
          <HypothesisEntry key={h.id} h={h} steps={a.verification_steps.filter((s) => s.hypothesis_id === h.id)} />
        ))}
        {orphanSteps.length > 0 && (
          <>
            <Stage title="Other verification steps" hint="never executed by ResolveAI" />
            <Entry>
              <ol className="max-w-[75ch] space-y-4">
                {orphanSteps.map((s) => (
                  <StepItem key={s.id} s={s} />
                ))}
              </ol>
            </Entry>
          </>
        )}
        {a.missing_information.length > 0 && (
          <>
            <Stage title="Missing information" count={a.missing_information.length} />
            <Entry>
              <ul className="max-w-[75ch] list-disc space-y-1 pl-5 text-sm text-ink-2">
                {a.missing_information.map((m, i) => (
                  <li key={i}>{m}</li>
                ))}
              </ul>
            </Entry>
          </>
        )}
        <Entry person>
          <h3 className="text-accent">Reviewer decision</h3>
          <p className="mt-1 max-w-[75ch] text-sm text-ink-2">
            {confirmed ? "A reviewer has confirmed the root cause in the RCA." : "Nothing above is confirmed. A reviewer runs the checks, then confirms the root cause in the RCA."}{" "}
            Verification steps are suggestions only and are never executed by ResolveAI.
          </p>
          <Button variant="secondary" size="sm" className="mt-3" onClick={onReview}>
            Open the RCA
            <Icon name="chevronRight" />
          </Button>
        </Entry>
      </ol>
      {a.safety_warnings.length > 0 && (
        <Alert tone="danger" title="Safety warnings">
          <ul className="list-disc space-y-1 pl-5">
            {a.safety_warnings.map((w, i) => (
              <li key={i}>
                {w.command && <code className="measured">{w.command}</code>} {w.reason}
              </li>
            ))}
          </ul>
        </Alert>
      )}
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
      icon={rca ? "refresh" : "sparkle"}
      disabled={!analysisId || !!busy}
      loading={busy === "rca"}
      onClick={() => run("rca", () => post(`/incidents/${incidentId}/rca`, { analysis_id: analysisId }))}
    >
      {busy === "rca" ? "Generating…" : rca ? "Regenerate draft" : "Generate RCA draft"}
    </Button>
  );
  if (!rca || !body) {
    return (
      <EmptyState
        title="No RCA draft yet"
        description={analysisId ? "Generate a structured draft from the latest analysis. It stays unconfirmed until a reviewer signs off." : "RCA drafts are generated from an analysis. Run one first."}
        action={
          analysisId ? (
            generate("primary")
          ) : (
            <Button variant="secondary" onClick={onNeedAnalysis}>
              Go to analysis
              <Icon name="chevronRight" />
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
    );

  const text = (k: TextKey, label: string, rows = 3, hint?: string) => (
    <Field label={label} hint={hint}>
      {(p) => <textarea {...p} className={input} rows={rows} value={body[k]} onChange={(e) => setBody({ ...body, [k]: e.target.value })} />}
    </Field>
  );
  const rawField = (k: keyof typeof raw, label: string, hint: string, mono = false) => (
    <Field label={label} hint={hint}>
      {(p) => <textarea {...p} className={cx(input, mono && "measured")} rows={4} value={raw[k]} onChange={(e) => setRaw({ ...raw, [k]: e.target.value })} />}
    </Field>
  );

  return (
    <div className="grid gap-[var(--gap-columns)] lg:grid-cols-[minmax(0,1fr)_20rem]">
      <div className="min-w-0 space-y-6">
        <Alert tone="info">
          <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <AiLabel /> Draft generated from the analysis; edit freely. It stays UNCONFIRMED because the model only suggests a cause. A person confirms it with the review panel, after writing the confirmed cause and its evidence.
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
          <div className="grid gap-5 md:grid-cols-2">
            <div className="space-y-2">
              <Badge value="suspected">Written by the model</Badge>
              {text("suspected_cause", "Suspected cause (unconfirmed)", 4)}
            </div>
            <div className="space-y-2">
              <Badge value="reviewer" tone="person">
                Written by the reviewer
              </Badge>
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
      <aside className="lg:sticky lg:top-10 lg:self-start">
        <Card title="Review" description={confirmed ? "This RCA has been confirmed by a reviewer." : "Root cause is not confirmed."}>
          <div className="space-y-5">
            <ol className="flex items-center gap-3 text-sm" aria-label="RCA status">
              <li className={confirmed ? "text-muted" : "text-accent"} aria-current={confirmed ? undefined : "step"}>
                <span className="measured mr-1.5">1</span>Draft
              </li>
              <li className="h-px flex-1 bg-rule-2" aria-hidden="true" />
              <li className={confirmed ? "text-ok" : "text-muted"} aria-current={confirmed ? "step" : undefined}>
                <span className="measured mr-1.5">2</span>Confirmed
              </li>
            </ol>
            <div className="flex flex-wrap gap-2">
              <Badge value={rca.status} />
              <Badge value={rca.cause_status}>Cause {rca.cause_status.toLowerCase()}</Badge>
            </div>
            {rca.reviewed_at && rca.reviewer_email && (
              <p className="text-sm text-ink-2">
                Reviewed by <span className="measured text-accent">{rca.reviewer_email}</span> at{" "}
                <span className="measured">{new Date(rca.reviewed_at).toLocaleString()}</span>.
              </p>
            )}
            <div className="grid gap-2 border-t border-rule pt-5">
              <Button variant="secondary" disabled={!dirty || !!busy} loading={busy === "save"} onClick={save}>
                {busy === "save" ? "Saving…" : "Save draft"}
              </Button>
              <p className="text-xs text-muted" role="status">
                {dirty ? `Unsaved changes.${confirmed ? " Saving resets the review to UNCONFIRMED." : ""}` : "No unsaved changes."}
              </p>
              <a className={btn("secondary")} href={`/api/v1/incidents/${incidentId}/rca/export`}>
                <Icon name="download" />
                Export Markdown
              </a>
              {generate("secondary")}
            </div>
            {!confirmed && (
              <div className="space-y-4 border-t border-rule pt-5">
                <h3>Before confirming</h3>
                <ul className="space-y-2 text-sm">
                  {gates.map(([label, ok]) => (
                    <li key={label} className={cx("flex items-start gap-2", ok ? "text-ink-2" : "text-muted")}>
                      {ok ? <Icon name="check" className="mt-1 h-4 w-4 text-ok" /> : <span className="mt-1 h-4 w-4 shrink-0 rounded-chip border border-edge" aria-hidden="true" />}
                      {label}
                      <span className="visually-hidden">{ok ? "(done)" : "(to do)"}</span>
                    </li>
                  ))}
                </ul>
                <label className="flex items-start gap-3 text-sm text-ink-2">
                  <input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} className="mt-1 h-4 w-4 shrink-0 accent-accent" />
                  <span>I have reviewed the verification evidence and confirm the cause stated in “Confirmed cause”. This records me as reviewer with a timestamp.</span>
                </label>
                <Button
                  className="w-full"
                  icon="check"
                  disabled={!canConfirm || !!busy}
                  loading={busy === "confirm"}
                  onClick={() => run("confirm", () => post(`/incidents/${incidentId}/rca/confirm`, { reviewer_acknowledgement: true, expected_updated_at: rca.updated_at }))}
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
