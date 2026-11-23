export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public requestId?: string,
  ) {
    super(message);
  }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const res = await fetch(`/api/v1${path}`, { ...init, headers, credentials: "same-origin" });
  if (res.status === 401 && typeof window !== "undefined" && !path.startsWith("/auth/")) {
    window.location.assign("/login?expired=1"); // full reload drops in-memory state after expiry
  }
  if (!res.ok) {
    let code = "HTTP_ERROR";
    let message = `Request failed (${res.status})`;
    let requestId: string | undefined;
    try {
      const body = await res.json();
      code = body.error?.code ?? code;
      message = body.error?.message ?? message;
      requestId = body.error?.request_id;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, code, message, requestId);
  }
  if (res.status === 204) return undefined as T;
  const type = res.headers.get("content-type") ?? "";
  return (type.includes("application/json") ? res.json() : res.text()) as Promise<T>;
}

export const post = <T>(path: string, body?: unknown) =>
  api<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });
export const patch = <T>(path: string, body: unknown) =>
  api<T>(path, { method: "PATCH", body: JSON.stringify(body) });

export function errorText(e: unknown): string {
  if (e instanceof ApiError) return `${e.message} (${e.code}${e.requestId ? `, request ${e.requestId}` : ""})`;
  return "Unexpected error. Please retry.";
}

export type Page<T> = { items: T[]; total: number; limit: number; offset: number };

export type DocumentMeta = {
  id: string;
  filename: string;
  mime_type: string;
  size_bytes: number;
  status: "queued" | "processing" | "ready" | "failed";
  page_count: number | null;
  chunk_count: number | null;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
};

export type Chunk = {
  id: string;
  document_id: string;
  document_filename: string;
  page_number: number;
  chunk_index: number;
  text: string;
};

export type Citation = { document_id: string; chunk_id: string; page: number; quote: string; filename: string };

export type ChatResponse = {
  answer: string;
  abstained: boolean;
  citations: Citation[];
  conversation_id: string;
  request_id: string;
  safety_warnings: string[];
  usage: { input_tokens: number; output_tokens: number; estimated_cost_usd: number | null; provider: string; model: string };
  retrieval: { top_k: number; retrieved: { chunk_id: string; score: number }[]; citations_rejected: number };
};

export type Observation = { id: string; source: string; line_number?: number | null; excerpt: string; category: string; interpretation?: string | null };
export type Hypothesis = { id: string; title: string; explanation: string; supporting_evidence: string[]; contradicting_evidence: string[]; confidence: string; status: string };
export type Step = { id: string; hypothesis_id?: string | null; command_or_check: string; read_only: boolean; expected_result: string; interpretation: string };
export type Analysis = {
  id: string;
  observations: Observation[];
  hypotheses: Hypothesis[];
  verification_steps: Step[];
  missing_information: string[];
  safety_warnings: { command?: string | null; reason: string }[];
  evidence: { chunk_id: string; document_id?: string; filename?: string; page_number?: number; score?: number }[];
  provider: string;
  model: string;
  created_at: string;
  disclaimer?: string;
};

export type RcaBody = {
  incident_summary: string;
  customer_impact: string;
  timeline: { time?: string | null; event: string; source: string }[];
  detection: string;
  resolution: string;
  suspected_cause: string;
  confirmed_cause: string;
  corrective_actions: string[];
  preventive_actions: string[];
  evidence_appendix: { ref: string; excerpt: string }[];
};

export type Rca = {
  id: string;
  incident_id: string;
  analysis_id: string | null;
  body_json: RcaBody;
  status: "DRAFT" | "REVIEWED";
  cause_status: "UNCONFIRMED" | "CONFIRMED";
  reviewer_id: string | null;
  reviewed_at: string | null;
  updated_at: string;
};

export type Incident = {
  id: string;
  title: string;
  severity: string;
  service: string;
  symptoms: string;
  environment: string | null;
  started_at: string | null;
  detected_at: string | null;
  sanitized_log: string | null;
  redaction_summary: Record<string, number> | null;
  status: string;
  created_at: string;
};

export type IncidentDetail = Incident & { latest_analysis: Analysis | null; rca: Rca | null };
