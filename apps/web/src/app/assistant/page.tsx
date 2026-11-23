"use client";

import { useState } from "react";
import { AiLabel, Card, Empty, ErrorBox, Highlight, button, input } from "@/components/ui";
import { ApiError, api, errorText, post, type ChatResponse, type Chunk, type Citation } from "@/lib/api";

type Turn = { question: string; response?: ChatResponse; error?: string };
type Preview = { citation: Citation; chunk?: Chunk; removed?: boolean };

export default function Assistant() {
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState<Preview | null>(null);

  async function ask(e: React.FormEvent) {
    e.preventDefault();
    const q = question.trim();
    if (!q) return;
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

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_380px]">
      <div className="space-y-4">
        <h1 className="text-2xl font-bold">Assistant</h1>
        {turns.length === 0 && <Empty>Ask a question about your uploaded SOPs, e.g. “What does connect() failed (111: Connection refused) mean?”</Empty>}
        {turns.map((t, i) => (
          <div key={i} className="space-y-2">
            <p className="ml-auto max-w-[80%] rounded-lg bg-slate-900 px-3 py-2 text-sm text-white">{t.question}</p>
            {t.error && <ErrorBox message={t.error} />}
            {!t.response && !t.error && <p className="text-sm text-slate-500">Retrieving evidence…</p>}
            {t.response && <Answer r={t.response} onCite={openCitation} />}
          </div>
        ))}
        <form onSubmit={ask} className="flex gap-2">
          <input className={input} value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="Ask about an SOP or symptom…" maxLength={2000} aria-label="Question" />
          <button className={button} disabled={busy || !question.trim()}>Ask</button>
        </form>
      </div>
      <aside className="lg:sticky lg:top-4 lg:self-start">
        <Card title="Source excerpt">
          {!preview ? (
            <Empty>Click a citation to inspect the exact supporting excerpt.</Empty>
          ) : preview.removed ? (
            <p className="text-sm text-slate-600">Source removed — the cited document was deleted.</p>
          ) : !preview.chunk ? (
            <p className="text-sm text-slate-500">Loading…</p>
          ) : (
            <div className="space-y-2 text-sm">
              <p className="text-xs text-slate-500">
                {preview.chunk.document_filename} · page {preview.chunk.page_number} · chunk {preview.chunk.chunk_index}
              </p>
              <div className="max-h-[60vh] overflow-y-auto rounded border border-slate-200 bg-slate-50 p-3">
                <Highlight text={preview.chunk.text} quote={preview.citation.quote} />
              </div>
            </div>
          )}
        </Card>
      </aside>
    </div>
  );
}

function Answer({ r, onCite }: { r: ChatResponse; onCite: (c: Citation) => void }) {
  return (
    <div className="max-w-[90%] space-y-2 rounded-lg border border-slate-200 bg-white p-3 text-sm shadow-sm">
      <div className="flex items-center gap-2">
        <AiLabel />
        {r.abstained && <span className="rounded bg-amber-100 px-2 py-0.5 text-xs text-amber-800">Insufficient evidence</span>}
      </div>
      <p className="whitespace-pre-wrap">{r.answer.replace(/\s*\[chunk:[^\]]+\]/g, "")}</p>
      {r.safety_warnings.length > 0 && (
        <p className="rounded bg-red-50 p-2 text-xs text-red-700">
          Safety: this answer mentions state-changing commands. Do not run them without human approval.
        </p>
      )}
      {r.citations.length > 0 && (
        <ol className="space-y-1">
          {r.citations.map((c, i) => (
            <li key={c.chunk_id + i}>
              <button onClick={() => onCite(c)} className="text-left text-xs text-blue-700 hover:underline">
                [{i + 1}] {c.filename} p.{c.page}: “{c.quote}”
              </button>
            </li>
          ))}
        </ol>
      )}
      <p className="text-[11px] text-slate-400">
        {r.usage.provider}/{r.usage.model} · {r.usage.input_tokens}+{r.usage.output_tokens} tokens · est. $
        {(r.usage.estimated_cost_usd ?? 0).toFixed(5)} · {r.retrieval.retrieved.length} chunks retrieved
        {r.retrieval.citations_rejected > 0 && ` · ${r.retrieval.citations_rejected} citation(s) rejected by validator`} · request {r.request_id}
      </p>
    </div>
  );
}
