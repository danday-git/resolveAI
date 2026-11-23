"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Icon } from "@/components/icons";
import {
  Badge,
  Button,
  Card,
  Dialog,
  EmptyState,
  ErrorBox,
  LoadingRows,
  PageHeader,
  Spinner,
  cx,
  input,
  td,
  th,
  useToast,
} from "@/components/ui";
import { api, errorText, type DocumentChunkPreview, type DocumentMeta, type Page } from "@/lib/api";

const MAX_MB = 10;
const ACCEPT = ".pdf,.txt,.md,application/pdf,text/plain,text/markdown";
const kb = (n: number) => (n < 1024 * 1024 ? `${Math.max(1, Math.round(n / 1024))} KB` : `${(n / 1024 / 1024).toFixed(1)} MB`);

export default function KnowledgeBase() {
  const toast = useToast();
  const [docs, setDocs] = useState<DocumentMeta[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState<string | null>(null);
  const [drag, setDrag] = useState(false);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const [preview, setPreview] = useState<{ doc: DocumentMeta; chunks: DocumentChunkPreview[] | null } | null>(null);
  const [pendingDelete, setPendingDelete] = useState<DocumentMeta | null>(null);
  const [deleting, setDeleting] = useState(false);
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
    if (file.size > MAX_MB * 1024 * 1024) return setError(`${file.name} exceeds the ${MAX_MB} MB limit.`);
    const form = new FormData();
    form.append("file", file);
    setUploading(file.name);
    try {
      await api("/documents", { method: "POST", body: form });
      toast("success", `${file.name} uploaded — indexing started.`);
      load();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setUploading(null);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  async function confirmDelete() {
    const d = pendingDelete;
    if (!d) return;
    setDeleting(true);
    try {
      await api(`/documents/${d.id}`, { method: "DELETE" });
      if (preview?.doc.id === d.id) setPreview(null);
      toast("success", `${d.filename} deleted.`);
      load();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setDeleting(false);
      setPendingDelete(null);
    }
  }

  async function open(d: DocumentMeta) {
    setPreview({ doc: d, chunks: null });
    try {
      const p = await api<Page<DocumentChunkPreview>>(`/documents/${d.id}/chunks?limit=100`);
      setPreview({ doc: d, chunks: p.items });
    } catch (e) {
      setPreview(null);
      setError(errorText(e));
    }
  }

  const visible = useMemo(
    () =>
      (docs ?? []).filter(
        (d) =>
          d.filename.toLowerCase().includes(query.trim().toLowerCase()) &&
          (status === "all" || d.status === status || (status === "processing" && d.status === "queued")),
      ),
    [docs, query, status],
  );

  const actions = (d: DocumentMeta) => (
    <div className="flex justify-end gap-1.5">
      <Button variant="secondary" size="sm" icon="eye" disabled={d.status !== "ready"} onClick={() => open(d)} aria-label={`Preview ${d.filename}`}>
        Preview
      </Button>
      <Button variant="danger" size="sm" icon="trash" onClick={() => setPendingDelete(d)} aria-label={`Delete ${d.filename}`}>
        <span className="sr-only sm:not-sr-only">Delete</span>
      </Button>
    </div>
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title="Knowledge Base"
        description="Runbooks and SOPs the assistant may cite. Documents are only visible to you."
        actions={
          <Button icon="upload" loading={!!uploading} onClick={() => fileRef.current?.click()}>
            Upload document
          </Button>
        }
      />
      <input
        ref={fileRef}
        type="file"
        accept={ACCEPT}
        aria-label="Document file"
        className="sr-only"
        tabIndex={-1}
        onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])}
      />
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          const f = e.dataTransfer.files?.[0];
          if (f) upload(f);
        }}
        className={cx(
          "flex flex-col items-center gap-2 rounded-card border-2 border-dashed px-4 py-6 text-center transition-colors sm:flex-row sm:text-left",
          drag ? "border-indigo-400 bg-indigo-50" : "border-zinc-300 bg-white",
        )}
      >
        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-zinc-100 text-zinc-500">
          {uploading ? <Spinner /> : <Icon name="upload" className="h-5 w-5" />}
        </span>
        <div className="flex-1 text-sm">
          {uploading ? (
            <p className="font-medium text-zinc-800">Uploading {uploading}…</p>
          ) : (
            <p className="font-medium text-zinc-800">
              Drop a file here, or{" "}
              <button type="button" className="text-indigo-700 underline-offset-2 hover:underline" onClick={() => fileRef.current?.click()}>
                browse
              </button>
            </p>
          )}
          <p className="text-xs text-zinc-500">
            Text-based PDF, TXT or MD up to {MAX_MB} MB. Scanned PDFs (OCR) are not supported. Use synthetic or permitted documents only.
          </p>
        </div>
      </div>
      <ErrorBox message={error} />
      <Card flush>
        <div className="flex flex-col gap-2 border-b border-zinc-100 p-3 sm:flex-row sm:items-center sm:px-4">
          <div className="relative flex-1">
            <Icon name="search" className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-400" />
            <input className={`${input} pl-9`} placeholder="Search by filename" value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Search documents" />
          </div>
          <select className={`${input} sm:w-44`} value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Filter by status">
            <option value="all">All statuses</option>
            <option value="ready">Ready</option>
            <option value="processing">Processing</option>
            <option value="failed">Failed</option>
          </select>
        </div>
        {docs === null ? (
          <div className="p-5">
            <LoadingRows rows={4} label="Loading documents" />
          </div>
        ) : docs.length === 0 ? (
          <div className="p-5">
            <EmptyState icon="book" title="No documents yet" description="Upload an SOP or runbook to get started." />
          </div>
        ) : visible.length === 0 ? (
          <div className="p-5">
            <EmptyState icon="search" title="No matching documents" description="Try a different filename or status filter." />
          </div>
        ) : (
          <>
            <div className="hidden overflow-x-auto md:block">
            <table className="w-full text-sm">
              <thead className="border-b border-zinc-100 bg-zinc-50/60">
                <tr>
                  <th className={th}>File</th>
                  <th className={th}>Status</th>
                  <th className={cx(th, "text-right")}>Pages</th>
                  <th className={cx(th, "text-right")}>Chunks</th>
                  <th className={cx(th, "hidden xl:table-cell")}>Uploaded</th>
                  <th className={th}>
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {visible.map((d) => (
                  <tr key={d.id} className="hover:bg-zinc-50/60">
                    <td className={td}>
                      <div className="flex items-center gap-2.5">
                        <Icon name="file" className="h-4 w-4 text-zinc-400" />
                        <div className="min-w-0">
                          <p className="truncate font-medium text-zinc-900">{d.filename}</p>
                          <p className="text-xs text-zinc-500">{kb(d.size_bytes)}</p>
                        </div>
                      </div>
                    </td>
                    <td className={td}>
                      <Badge value={d.status} />
                      {d.error_code && (
                        <p className="mt-1 text-xs text-red-700" title={d.error_message ?? ""}>
                          {d.error_code}
                        </p>
                      )}
                    </td>
                    <td className={cx(td, "text-right tabular-nums")}>{d.page_count ?? "–"}</td>
                    <td className={cx(td, "text-right tabular-nums")}>{d.chunk_count ?? "–"}</td>
                    <td className={cx(td, "hidden whitespace-nowrap text-xs text-zinc-500 xl:table-cell")}>{new Date(d.created_at).toLocaleString()}</td>
                    <td className={td}>{actions(d)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
            <ul className="divide-y divide-zinc-100 md:hidden">
              {visible.map((d) => (
                <li key={d.id} className="space-y-2 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <p className="min-w-0 break-all text-sm font-medium text-zinc-900">{d.filename}</p>
                    <Badge value={d.status} />
                  </div>
                  <p className="text-xs text-zinc-500">
                    {d.page_count ?? "–"} pages · {d.chunk_count ?? "–"} chunks · {kb(d.size_bytes)} · {new Date(d.created_at).toLocaleDateString()}
                  </p>
                  {d.error_code && <p className="text-xs text-red-700">{d.error_code}: {d.error_message}</p>}
                  {actions(d)}
                </li>
              ))}
            </ul>
          </>
        )}
      </Card>
      <Dialog
        open={!!preview}
        onClose={() => setPreview(null)}
        wide
        title={preview ? `Source preview — ${preview.doc.filename}` : ""}
        description={preview?.chunks ? `${preview.chunks.length} indexed chunks` : undefined}
      >
        {!preview?.chunks ? (
          <LoadingRows rows={5} label="Loading chunks" />
        ) : (
          <ol className="space-y-3">
            {preview.chunks.map((c) => (
              <li key={c.id} className="rounded-card border border-zinc-200 bg-zinc-50/60 p-3 text-sm">
                <p className="mb-1.5 text-xs font-medium text-zinc-500">
                  Page {c.page_number} · chunk {c.chunk_index} · {c.token_count} tokens
                </p>
                <p className="whitespace-pre-wrap leading-relaxed">{c.text_preview}</p>
              </li>
            ))}
          </ol>
        )}
      </Dialog>
      <Dialog
        open={!!pendingDelete}
        onClose={() => setPendingDelete(null)}
        title="Delete document?"
        description={pendingDelete ? `${pendingDelete.filename} and all of its indexed chunks will be permanently removed. Citations to it will show as removed.` : undefined}
        footer={
          <>
            <Button variant="secondary" onClick={() => setPendingDelete(null)}>
              Cancel
            </Button>
            <Button variant="danger" icon="trash" loading={deleting} onClick={confirmDelete}>
              Delete document
            </Button>
          </>
        }
      />
    </div>
  );
}
