"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { Badge, Button, Dialog, EmptyState, ErrorBox, LoadingRows, PageHeader, Pager, cx, input, td, th } from "@/components/ui";
import { PAGE_SIZE, pageNumber, useDebounced, useQueryState } from "@/lib/url";
import { api, errorText, type DocumentChunkPreview, type DocumentMeta, type DocumentPage, type Page } from "@/lib/api";

const MAX_MB = 10;
const ACCEPT = ".pdf,.txt,.md,application/pdf,text/plain,text/markdown";
const kb = (n: number) => (n < 1024 * 1024 ? `${Math.max(1, Math.round(n / 1024))} KB` : `${(n / 1024 / 1024).toFixed(1)} MB`);

function KnowledgeBase() {
  const [list, setList] = useState<DocumentPage | null>(null);
  const [tick, setTick] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState<string | null>(null);
  const [drag, setDrag] = useState(false);
  const [query, setQuery] = useQueryState("q");
  const [status, setStatus] = useQueryState("status", "all");
  const [preview, setPreview] = useState<{ doc: DocumentMeta; chunks: DocumentChunkPreview[] | null } | null>(null);
  const [pendingDelete, setPendingDelete] = useState<DocumentMeta | null>(null);
  const [deleting, setDeleting] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const [pageParam, setPage] = useQueryState("page", "1");
  const page = pageNumber(pageParam);
  const q = useDebounced(query.trim());
  const load = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    const params = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String((page - 1) * PAGE_SIZE) });
    if (q) params.set("q", q);
    if (status === "processing") params.append("status", "queued");
    if (status !== "all") params.append("status", status);
    let current = true; // a slower, older response must not replace a newer one
    api<DocumentPage>(`/documents?${params}`)
      .then((p) => {
        if (!current) return;
        // The page no longer exists (a delete or filter shortened the list): fall back to the last one.
        if (!p.items.length && p.total) setPage(String(Math.ceil(p.total / PAGE_SIZE)));
        else setList(p);
      })
      .catch((e) => current && setError(errorText(e)));
    return () => {
      current = false;
    };
  }, [q, status, page, tick, setPage]);
  const docs = list?.items ?? null;
  const filtered = q !== "" || status !== "all";

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
      load();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setDeleting(false);
      setPendingDelete(null);
    }
  }

  async function open(d: DocumentMeta) {
    if (preview?.doc.id === d.id) return setPreview(null);
    setPreview({ doc: d, chunks: null });
    try {
      const p = await api<Page<DocumentChunkPreview>>(`/documents/${d.id}/chunks?limit=100`);
      setPreview({ doc: d, chunks: p.items });
    } catch (e) {
      setPreview(null);
      setError(errorText(e));
    }
  }


  const actions = (d: DocumentMeta) => (
    <div className="flex justify-end gap-2">
      <Button
        variant="secondary"
        size="sm"
        disabled={d.status !== "ready"}
        title={d.status === "ready" ? undefined : "Available once indexing finishes"}
        onClick={() => open(d)}
        aria-label={`Preview ${d.filename}`}
        aria-expanded={preview?.doc.id === d.id}
      >
        {preview?.doc.id === d.id ? "Hide" : "Preview"}
      </Button>
      <Button variant="danger" size="sm" onClick={() => setPendingDelete(d)} aria-label={`Delete ${d.filename}`}>
        Delete
      </Button>
    </div>
  );

  // The indexed chunks open in place under their document, so the list stays in view.
  const chunks = (d: DocumentMeta) =>
    preview?.doc.id === d.id && (
      <div className="rounded-card border border-rule bg-paper-2" role="region" aria-label={`Source preview of ${d.filename}`}>
        {!preview.chunks ? (
          <div className="p-5">
            <LoadingRows rows={4} label="Loading chunks" />
          </div>
        ) : (
          <>
            <p className="border-b border-rule px-5 py-3 text-sm text-muted">
              <span className="measured text-ink-2">{preview.chunks.length}</span> indexed chunks
            </p>
            <ol className="max-h-[28rem] overflow-y-auto">
              {preview.chunks.map((c) => (
                <li key={c.id} className="grid gap-x-6 gap-y-2 border-b border-rule px-5 py-4 last:border-0 sm:grid-cols-[9rem_minmax(0,1fr)]">
                  <dl className="measured flex gap-x-4 text-cool sm:flex-col">
                    <div>
                      <dt className="visually-hidden">Location</dt>
                      <dd>
                        Page {c.page_number}, chunk {c.chunk_index}
                      </dd>
                    </div>
                    <div>
                      <dt className="visually-hidden">Size</dt>
                      <dd className="text-muted">{c.token_count} tokens</dd>
                    </div>
                  </dl>
                  <p className="max-w-[75ch] whitespace-pre-wrap text-sm text-ink-2">{c.text_preview}</p>
                </li>
              ))}
            </ol>
          </>
        )}
      </div>
    );

  return (
    <div className="space-y-6">
      <PageHeader
        title="Knowledge Base"
        description="Runbooks and SOPs the assistant may cite. Documents are only visible to you."
        actions={
          <Button loading={!!uploading} onClick={() => fileRef.current?.click()}>
            Upload document
          </Button>
        }
      />
      <input
        ref={fileRef}
        type="file"
        accept={ACCEPT}
        aria-label="Document file"
        className="visually-hidden"
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
          "flex flex-wrap items-center justify-between gap-x-6 gap-y-3 rounded-card border border-dashed px-5 py-4 transition-colors duration-[var(--dur-micro)]",
          drag ? "border-accent bg-accent-soft" : "border-rule-2",
        )}
      >
        <div className="min-w-0 text-sm">
          <p className="text-ink" role="status">
            {uploading ? `Uploading ${uploading}…` : "Drop a file here to add it to the knowledge base."}
          </p>
          <p className="mt-1 max-w-[75ch] text-muted">
            Text-based PDF, TXT or MD up to {MAX_MB}&nbsp;MB. Scanned PDFs (OCR) are not supported. Use synthetic or permitted documents only.
          </p>
        </div>
        <Button variant="secondary" size="sm" disabled={!!uploading} onClick={() => fileRef.current?.click()}>
          Browse files
        </Button>
      </div>
      <ErrorBox message={error} />
      <div className="flex flex-col gap-2 sm:flex-row">
        <input className={`${input} sm:max-w-sm`} type="search" placeholder="Search by filename" value={query} onChange={(e) => {
            setQuery(e.target.value);
            setPage("1");
          }}
          aria-label="Search documents"
        />
        <select className={`${input} sm:w-44`} value={status} onChange={(e) => {
            setStatus(e.target.value);
            setPage("1");
          }}
          aria-label="Filter by status"
        >
          <option value="all">All statuses</option>
          <option value="ready">Ready</option>
          <option value="processing">Processing</option>
          <option value="failed">Failed</option>
        </select>
      </div>
      {docs === null ? (
        !error && <LoadingRows rows={4} label="Loading documents" />
      ) : docs.length === 0 && filtered ? (
        <EmptyState title="No matching documents" description="Try a different filename or status filter." />
      ) : docs.length === 0 ? (
        <EmptyState
          title="No documents yet"
          description="The assistant can only answer from what is uploaded here. Add an SOP or runbook to get started."
          action={
            <Button variant="secondary" size="sm" onClick={() => fileRef.current?.click()}>
              Upload document
            </Button>
          }
        />
      ) : (
        <>
          <table className="hidden w-full text-sm md:table">
            <thead>
              <tr>
                <th className={th}>File</th>
                <th className={th}>Status</th>
                <th className={cx(th, "text-right")}>Pages</th>
                <th className={cx(th, "text-right")}>Chunks</th>
                <th className={cx(th, "text-right")}>Size</th>
                <th className={cx(th, "hidden lg:table-cell")}>Uploaded</th>
                <th className={th}>
                  <span className="visually-hidden">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {docs.map((d) => (
                <FragmentRow key={d.id} open={preview?.doc.id === d.id} detail={chunks(d)}>
                  <td className={cx(td, "break-all text-ink")}>
                    {d.filename}
                    <p className="measured mt-0.5 text-xs text-muted lg:hidden">{new Date(d.created_at).toLocaleString()}</p>
                  </td>
                  <td className={td}>
                    <Badge value={d.status} />
                    {d.error_code && (
                      <p className="measured mt-1 text-xs text-error" title={d.error_message ?? ""}>
                        {d.error_code}
                      </p>
                    )}
                  </td>
                  <td className={cx(td, "measured text-right")}>{d.page_count ?? "–"}</td>
                  <td className={cx(td, "measured text-right")}>{d.chunk_count ?? "–"}</td>
                  <td className={cx(td, "measured whitespace-nowrap text-right text-ink-2")}>{kb(d.size_bytes)}</td>
                  <td className={cx(td, "measured hidden whitespace-nowrap text-ink-2 lg:table-cell")}>{new Date(d.created_at).toLocaleString()}</td>
                  <td className={cx(td, "py-2")}>{actions(d)}</td>
                </FragmentRow>
              ))}
            </tbody>
          </table>
          <ul className="border-t border-rule-2 md:hidden">
            {docs.map((d) => (
              <li key={d.id} className="space-y-3 border-b border-rule py-4">
                <div className="flex items-start justify-between gap-3">
                  <p className="min-w-0 break-all text-ink">{d.filename}</p>
                  <Badge value={d.status} />
                </div>
                <dl className="grid grid-cols-[auto_1fr_auto_1fr] gap-x-4 gap-y-1 text-sm">
                  <dt className="text-muted">Pages</dt>
                  <dd className="measured">{d.page_count ?? "–"}</dd>
                  <dt className="text-muted">Chunks</dt>
                  <dd className="measured">{d.chunk_count ?? "–"}</dd>
                  <dt className="text-muted">Size</dt>
                  <dd className="measured">{kb(d.size_bytes)}</dd>
                  <dt className="text-muted">Uploaded</dt>
                  <dd className="measured">{new Date(d.created_at).toLocaleString()}</dd>
                </dl>
                {d.error_code && (
                  <p className="text-sm text-error">
                    <span className="measured">{d.error_code}</span> {d.error_message}
                  </p>
                )}
                {actions(d)}
                {chunks(d)}
              </li>
            ))}
          </ul>
        </>
      )}
      {list && <Pager page={page} total={list.total} size={PAGE_SIZE} onChange={(p) => setPage(String(p))} />}
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
            <Button variant="danger" loading={deleting} onClick={confirmDelete}>
              Delete document
            </Button>
          </>
        }
      />
    </div>
  );
}

function FragmentRow({ open, detail, children }: { open: boolean; detail: React.ReactNode; children: React.ReactNode }) {
  return (
    <>
      <tr className={open ? "[&>td]:border-transparent" : undefined}>{children}</tr>
      {open && (
        <tr>
          <td colSpan={7} className="border-b border-rule pb-5">
            {detail}
          </td>
        </tr>
      )}
    </>
  );
}

export default function KnowledgeBasePage() {
  return (
    <Suspense>
      <KnowledgeBase />
    </Suspense>
  );
}
