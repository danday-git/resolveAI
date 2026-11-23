"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Badge, Card, Empty, ErrorBox, button, buttonSecondary } from "@/components/ui";
import {
  api,
  errorText,
  type DocumentChunkPreview,
  type DocumentMeta,
  type Page,
} from "@/lib/api";

const MAX_MB = 10;

export default function KnowledgeBase() {
  const [docs, setDocs] = useState<DocumentMeta[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [preview, setPreview] = useState<{
    doc: DocumentMeta;
    chunks: DocumentChunkPreview[];
  } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const load = useCallback(() => {
    api<Page<DocumentMeta>>("/documents?limit=100")
      .then((p) => setDocs(p.items))
      .catch((e) => setError(errorText(e)));
  }, []);

  useEffect(load, [load]);
  useEffect(() => {
    if (!docs?.some((d) => d.status === "queued" || d.status === "processing")) return;
    const t = setTimeout(load, 1500);
    return () => clearTimeout(t);
  }, [docs, load]);

  async function upload(file: File) {
    setError(null);
    if (file.size > MAX_MB * 1024 * 1024) return setError(`File exceeds ${MAX_MB} MB.`);
    const form = new FormData();
    form.append("file", file);
    setUploading(true);
    try {
      await api("/documents", { method: "POST", body: form });
      load();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  async function remove(d: DocumentMeta) {
    if (!confirm(`Delete ${d.filename} and all its indexed chunks?`)) return;
    try {
      await api(`/documents/${d.id}`, { method: "DELETE" });
      if (preview?.doc.id === d.id) setPreview(null);
      load();
    } catch (e) {
      setError(errorText(e));
    }
  }

  async function open(d: DocumentMeta) {
    try {
      const p = await api<Page<DocumentChunkPreview>>(`/documents/${d.id}/chunks?limit=100`);
      setPreview({ doc: d, chunks: p.items });
    } catch (e) {
      setError(errorText(e));
    }
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Knowledge Base</h1>
      <Card title="Upload document">
        <div className="flex flex-wrap items-center gap-3">
          <input
            ref={fileRef}
            type="file"
            accept=".pdf,.txt,.md,application/pdf,text/plain,text/markdown"
            aria-label="Document file"
            disabled={uploading}
            onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])}
            className="text-sm"
          />
          <span className="text-xs text-slate-500">Text-based PDF, TXT or MD up to {MAX_MB} MB. Scanned PDFs (OCR) are not supported. Use synthetic or permitted documents only.</span>
        </div>
        {uploading && <p className="mt-2 text-sm text-slate-500">Uploading…</p>}
      </Card>
      <ErrorBox message={error} />
      <Card title="Documents">
        {docs === null ? (
          <p className="text-sm text-slate-500">Loading…</p>
        ) : docs.length === 0 ? (
          <Empty>No documents yet. Upload an SOP or runbook to get started.</Empty>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-xs uppercase text-slate-500">
                <tr><th className="py-2">File</th><th>Status</th><th>Pages</th><th>Chunks</th><th>Uploaded</th><th /></tr>
              </thead>
              <tbody>
                {docs.map((d) => (
                  <tr key={d.id} className="border-t border-slate-100">
                    <td className="py-2 font-medium">{d.filename}</td>
                    <td>
                      <Badge value={d.status} />
                      {d.error_code && <span className="ml-2 text-xs text-red-700" title={d.error_message ?? ""}>{d.error_code}</span>}
                    </td>
                    <td>{d.page_count ?? "–"}</td>
                    <td>{d.chunk_count ?? "–"}</td>
                    <td className="text-xs text-slate-500">{new Date(d.created_at).toLocaleString()}</td>
                    <td className="space-x-2 text-right">
                      <button className={buttonSecondary} disabled={d.status !== "ready"} onClick={() => open(d)}>Preview</button>
                      <button className={buttonSecondary} onClick={() => remove(d)}>Delete</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
      {preview && (
        <Card title={`Source preview — ${preview.doc.filename}`} actions={<button className={button} onClick={() => setPreview(null)}>Close</button>}>
          <ol className="space-y-3">
            {preview.chunks.map((c) => (
              <li key={c.id} className="rounded border border-slate-200 p-3 text-sm">
                <p className="mb-1 text-xs text-slate-500">Page {c.page_number} · chunk {c.chunk_index}</p>
                <p className="whitespace-pre-wrap">{c.text_preview}</p>
              </li>
            ))}
          </ol>
        </Card>
      )}
    </div>
  );
}
