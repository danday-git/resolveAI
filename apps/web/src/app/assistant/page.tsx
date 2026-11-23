"use client";

import { useEffect, useRef, useState } from "react";
import { Icon } from "@/components/icons";
import { AiLabel, Alert, Badge, Button, Card, Highlight, LoadingRows, PageHeader, Spinner, cx, input } from "@/components/ui";
import { ApiError, api, errorText, post, type ChatResponse, type Chunk, type Citation } from "@/lib/api";

type Turn = { question: string; response?: ChatResponse; error?: string };
type Preview = { citation: Citation; chunk?: Chunk; removed?: boolean };

const suggestions = [
  "What should I check first when Nginx returns 502 Bad Gateway?",
  "What does connect() failed (111: Connection refused) mean?",
  "How do I investigate high CPU on a backend host?",
];

export default function Assistant() {
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState<Preview | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns]);

  async function ask(q: string) {
    q = q.trim();
    if (!q || busy) return;
    setBusy(true);
    setQuestion("");
    setTurns((t) => [...t, { question: q }]);
    try {
      const r = await post<ChatResponse>("/chat", { question: q, conversation_id: conversationId });
      setConversationId(r.conversation_id);
      setTurns((t) => t.map((x, i) => (i === t.length - 1 ? { ...x, response: r } : x)));
    } catch (err) {
      const msg = err instanceof ApiError && err.code === "LLM_TIMEOUT" ? "The model timed out. Please retry." : errorText(err);
      setTurns((t) => t.map((x, i) => (i === t.length - 1 ? { ...x, error: msg } : x)));
    } finally {
      setBusy(false);
    }
  }

  async function openCitation(citation: Citation) {
    setPreview({ citation });
    try {
      const chunk = await api<Chunk>(`/chunks/${citation.chunk_id}`);
      setPreview({ citation, chunk });
    } catch (err) {
      setPreview({ citation, removed: err instanceof ApiError && err.status === 404 });
    }
  }

  const source = !preview ? (
    <p className="text-sm text-muted">No source selected. Choose a source under an answer to read the exact supporting excerpt.</p>
  ) : preview.removed ? (
    <Alert tone="warning" title="Source removed">
      The cited document was deleted.
    </Alert>
  ) : !preview.chunk ? (
    <LoadingRows rows={6} label="Loading source" />
  ) : (
    <div className="space-y-3">
      <dl className="measured grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1">
        <dt className="text-muted">File</dt>
        <dd className="break-all text-ink">{preview.chunk.document_filename}</dd>
        <dt className="text-muted">Page</dt>
        <dd className="text-cool">{preview.chunk.page_number}</dd>
        <dt className="text-muted">Chunk</dt>
        <dd className="text-cool">{preview.chunk.chunk_index}</dd>
      </dl>
      <div className="max-h-[60vh] overflow-y-auto rounded-pill border border-rule bg-paper-3 p-3 text-sm text-ink-2">
        <Highlight text={preview.chunk.text} quote={preview.citation.quote} />
      </div>
    </div>
  );

  return (
    <div className="grid gap-x-[var(--gap-columns)] lg:grid-cols-[minmax(0,1fr)_24rem]">
      <div className="flex min-h-[calc(100dvh-12rem)] min-w-0 flex-col">
        <PageHeader title="Assistant" description="Grounded answers from your knowledge base. Unsupported questions are declined, not guessed." />
        <div className="flex-1 pb-6">
          {turns.length === 0 && (
            <section>
              <h2>Try a question</h2>
              <ul className="mt-4 border-t border-rule">
                {suggestions.map((s) => (
                  <li key={s} className="flex items-center justify-between gap-4 border-b border-rule py-2.5">
                    <span className="min-w-0 text-ink-2">{s}</span>
                    <Button variant="secondary" size="sm" onClick={() => ask(s)} aria-label={`Ask: ${s}`}>
                      Ask
                    </Button>
                  </li>
                ))}
              </ul>
            </section>
          )}
          {turns.map((t, i) => (
            <article key={i} className="space-y-4 border-t border-rule py-6 first:border-0 first:pt-0">
              <div>
                <p className="text-sm text-accent">You asked</p>
                <p className="mt-1 max-w-[65ch] text-lg text-ink">{t.question}</p>
              </div>
              {t.error && <Alert tone="danger">{t.error}</Alert>}
              {!t.response && !t.error && (
                <p className="flex items-center gap-2 text-sm text-muted" role="status">
                  <Spinner /> Retrieving evidence…
                </p>
              )}
              {t.response && (
                <Answer
                  r={t.response}
                  onCite={openCitation}
                  active={preview?.citation}
                  source={t.response.citations.some((c) => c === preview?.citation) && <div className="rounded-card border border-rule bg-paper-2 p-4 lg:hidden">{source}</div>}
                />
              )}
            </article>
          ))}
          <div ref={endRef} />
        </div>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            ask(question);
          }}
          className="sticky bottom-0 border-t border-rule bg-paper pb-3 pt-3"
        >
          <div className="flex items-end gap-2">
            <textarea
              className={`${input} max-h-40 flex-1 resize-none`}
              rows={1}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                  e.preventDefault();
                  ask(question);
                }
              }}
              placeholder="Ask about an SOP or symptom…"
              maxLength={2000}
              aria-label="Question"
            />
            <Button type="submit" icon="send" loading={busy} disabled={!question.trim()}>
              Ask
            </Button>
          </div>
          <p className="mt-2 text-xs text-muted">Enter sends, Shift+Enter adds a new line. Documents are treated as untrusted data.</p>
        </form>
      </div>
      <aside className="hidden lg:block">
        <div className="sticky top-10">
          <Card title="Source excerpt" description="Exact text the citation was validated against.">
            {source}
          </Card>
        </div>
      </aside>
    </div>
  );
}

function Answer({ r, onCite, active, source }: { r: ChatResponse; onCite: (c: Citation) => void; active?: Citation; source?: React.ReactNode }) {
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <AiLabel />
        {r.abstained && <Badge value="Insufficient evidence" tone="person" />}
      </div>
      <p className="max-w-[70ch] whitespace-pre-wrap text-ink-2">{r.answer.replace(/\s*\[chunk:[^\]]+\]/g, "")}</p>
      {r.safety_warnings.length > 0 && (
        <Alert tone="danger" title="Safety">
          This answer mentions state-changing commands. Do not run them without human approval.
        </Alert>
      )}
      {r.citations.length > 0 && (
        <div>
          <h3 className="text-sm font-normal tracking-normal text-muted">Sources</h3>
          <ol className="mt-2 border-t border-rule">
            {r.citations.map((c, i) => {
              const on = active === c;
              return (
                <li key={c.chunk_id + i} className="border-b border-rule">
                  <button
                    onClick={() => onCite(c)}
                    aria-pressed={on}
                    className={cx(
                      "grid w-full grid-cols-[1.5rem_minmax(0,1fr)_auto] gap-x-2 px-2 py-2.5 text-left text-sm transition-colors duration-[var(--dur-micro)] hover:bg-paper-2 active:bg-rule",
                      on && "bg-paper-2",
                    )}
                  >
                    <span className="measured text-cool">{i + 1}</span>
                    <span className="min-w-0">
                      <span className="measured block break-all text-ink">
                        {c.filename}, page {c.page}
                      </span>
                      <span className="mt-0.5 line-clamp-2 block text-muted">“{c.quote}”</span>
                    </span>
                    <Icon name="chevronRight" className="mt-0.5 h-4 w-4 text-muted" />
                  </button>
                </li>
              );
            })}
          </ol>
        </div>
      )}
      {source}
      <details className="text-xs text-muted">
        <summary className="w-fit cursor-pointer select-none transition-colors hover:text-ink">Request details</summary>
        <dl className="measured mt-2 grid grid-cols-[auto_minmax(0,1fr)] gap-x-6 gap-y-1 text-xs">
          <dt>Model</dt>
          <dd className="text-cool">
            {r.usage.provider}/{r.usage.model}
          </dd>
          <dt>Retrieved</dt>
          <dd className="text-ink-2">{r.retrieval.retrieved.length} chunks</dd>
          {r.retrieval.citations_rejected > 0 && (
            <>
              <dt>Rejected</dt>
              <dd className="text-ink-2">{r.retrieval.citations_rejected} citation(s) rejected by validator</dd>
            </>
          )}
          <dt>Tokens</dt>
          <dd className="text-ink-2">
            {r.usage.input_tokens}+{r.usage.output_tokens}
          </dd>
          <dt>Est. cost</dt>
          <dd className="text-ink-2">${(r.usage.estimated_cost_usd ?? 0).toFixed(5)}</dd>
          <dt>Request</dt>
          <dd className="break-all text-ink-2">{r.request_id}</dd>
        </dl>
      </details>
    </div>
  );
}
