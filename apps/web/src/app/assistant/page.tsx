"use client";

import { useEffect, useRef, useState } from "react";
import { Icon } from "@/components/icons";
import { AiLabel, Alert, Button, Card, Dialog, EmptyState, Highlight, LoadingRows, PageHeader, Spinner, cx } from "@/components/ui";
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
  const [sheet, setSheet] = useState(false);
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
    if (!window.matchMedia("(min-width: 1024px)").matches) setSheet(true);
    try {
      const chunk = await api<Chunk>(`/chunks/${citation.chunk_id}`);
      setPreview({ citation, chunk });
    } catch (err) {
      setPreview({ citation, removed: err instanceof ApiError && err.status === 404 });
    }
  }

  const source = !preview ? (
    <EmptyState icon="quote" title="No source selected" description="Click a citation to inspect the exact supporting excerpt." />
  ) : preview.removed ? (
    <Alert tone="warning" title="Source removed">
      The cited document was deleted.
    </Alert>
  ) : !preview.chunk ? (
    <LoadingRows rows={6} label="Loading source" />
  ) : (
    <div className="space-y-3 text-sm">
      <div className="flex items-center gap-2 text-xs text-zinc-500">
        <Icon name="file" className="h-3.5 w-3.5" />
        <span className="truncate font-medium text-zinc-700">{preview.chunk.document_filename}</span>· page {preview.chunk.page_number} · chunk{" "}
        {preview.chunk.chunk_index}
      </div>
      <div className="max-h-[60vh] overflow-y-auto rounded-control border border-zinc-200 bg-zinc-50 p-3 leading-relaxed">
        <Highlight text={preview.chunk.text} quote={preview.citation.quote} />
      </div>
    </div>
  );

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
      <div className="flex min-h-[calc(100dvh-10rem)] flex-col">
        <PageHeader title="Assistant" description="Grounded answers from your knowledge base. Unsupported questions are declined, not guessed." />
        <div className="flex-1 space-y-5 pb-4">
          {turns.length === 0 && (
            <div className="rounded-card border border-zinc-200 bg-white p-5">
              <p className="text-sm font-medium text-zinc-800">Try a question</p>
              <div className="mt-3 flex flex-col gap-2">
                {suggestions.map((s) => (
                  <button
                    key={s}
                    onClick={() => ask(s)}
                    className="flex items-center gap-2 rounded-control border border-zinc-200 px-3 py-2 text-left text-sm text-zinc-700 transition-colors hover:border-indigo-300 hover:bg-indigo-50/50"
                  >
                    <Icon name="sparkle" className="h-4 w-4 text-indigo-500" />
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}
          {turns.map((t, i) => (
            <div key={i} className="space-y-3">
              <p className="ml-auto w-fit max-w-[85%] rounded-2xl rounded-br-md bg-zinc-900 px-4 py-2.5 text-sm text-white">{t.question}</p>
              {t.error && <Alert tone="danger">{t.error}</Alert>}
              {!t.response && !t.error && (
                <p className="flex items-center gap-2 text-sm text-zinc-500" role="status">
                  <Spinner /> Retrieving evidence…
                </p>
              )}
              {t.response && <Answer r={t.response} onCite={openCitation} active={preview?.citation} />}
            </div>
          ))}
          <div ref={endRef} />
        </div>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            ask(question);
          }}
          className="sticky bottom-0 -mx-1 bg-zinc-50/95 px-1 pb-2 pt-2 backdrop-blur"
        >
          <div className="flex items-end gap-2 rounded-card border border-zinc-300 bg-white p-2 shadow-sm focus-within:border-indigo-500 focus-within:ring-2 focus-within:ring-indigo-500/20">
            <textarea
              className="max-h-40 min-h-[2.5rem] flex-1 resize-none bg-transparent px-2 py-2 text-sm focus:outline-none"
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
            <Button type="submit" icon="send" loading={busy} disabled={!question.trim()} aria-label="Ask">
              <span className="hidden sm:inline">Ask</span>
            </Button>
          </div>
          <p className="mt-1.5 px-1 text-[11px] text-zinc-500">Enter to send · Shift+Enter for a new line · Documents are treated as untrusted data.</p>
        </form>
      </div>
      <aside className="hidden lg:block">
        <div className="sticky top-8">
          <Card title="Source excerpt" description="Exact text the citation was validated against.">
            {source}
          </Card>
        </div>
      </aside>
      <Dialog open={sheet} onClose={() => setSheet(false)} title="Source excerpt" description="Exact text the citation was validated against.">
        {source}
      </Dialog>
    </div>
  );
}

function Answer({ r, onCite, active }: { r: ChatResponse; onCite: (c: Citation) => void; active?: Citation }) {
  return (
    <div className="max-w-[95%] space-y-3 rounded-card border border-zinc-200 bg-white p-4 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <AiLabel />
        {r.abstained && <span className="rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-800 ring-1 ring-inset ring-amber-200">Insufficient evidence</span>}
      </div>
      <p className="whitespace-pre-wrap leading-relaxed text-zinc-800">{r.answer.replace(/\s*\[chunk:[^\]]+\]/g, "")}</p>
      {r.safety_warnings.length > 0 && (
        <Alert tone="danger" title="Safety">
          This answer mentions state-changing commands. Do not run them without human approval.
        </Alert>
      )}
      {r.citations.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-xs font-medium text-zinc-500">Sources</p>
          <ol className="space-y-1.5">
            {r.citations.map((c, i) => {
              const on = active?.chunk_id === c.chunk_id && active.quote === c.quote;
              return (
                <li key={c.chunk_id + i}>
                  <button
                    onClick={() => onCite(c)}
                    aria-pressed={on}
                    className={cx(
                      "flex w-full gap-2.5 rounded-control border px-3 py-2 text-left text-xs transition-colors",
                      on ? "border-indigo-300 bg-indigo-50" : "border-zinc-200 hover:border-zinc-300 hover:bg-zinc-50",
                    )}
                  >
                    <span className="grid h-5 w-5 shrink-0 place-items-center rounded bg-zinc-100 font-semibold text-zinc-600">{i + 1}</span>
                    <span className="min-w-0">
                      <span className="block font-medium text-zinc-800">
                        {c.filename} · p.{c.page}
                      </span>
                      <span className="line-clamp-2 text-zinc-500">“{c.quote}”</span>
                    </span>
                  </button>
                </li>
              );
            })}
          </ol>
        </div>
      )}
      <details className="text-[11px] text-zinc-500">
        <summary className="cursor-pointer select-none hover:text-zinc-600">
          {r.usage.provider}/{r.usage.model} · {r.retrieval.retrieved.length} chunks retrieved
          {r.retrieval.citations_rejected > 0 && ` · ${r.retrieval.citations_rejected} citation(s) rejected by validator`}
        </summary>
        <p className="mt-1 break-all">
          {r.usage.input_tokens}+{r.usage.output_tokens} tokens · est. ${(r.usage.estimated_cost_usd ?? 0).toFixed(5)} · request {r.request_id}
        </p>
      </details>
    </div>
  );
}
