# API reference

Base path `/api/v1`. Interactive OpenAPI docs: `http://localhost:8000/docs`. All data endpoints require `Authorization: Bearer <token>` or the `resolveai_session` cookie set by login.

Errors always look like `{"error": {"code": "...", "message": "...", "request_id": "..."}}`; every response carries `X-Request-ID`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/health`, `/ready` | Liveness; readiness checks DB, pgvector and embedding dimension. |
| POST | `/auth/login` | `{email, password}` → `{access_token, token_type, expires_at, user}` + session cookie. |
| POST | `/auth/logout` | Clears cookie. |
| GET | `/auth/me` | Current user. |
| POST | `/documents` | Multipart `file` (PDF/TXT/MD ≤ 10 MB) → 202 with `queued` document. Duplicate file → 409. |
| GET | `/documents` | Paginated list with status, chunk count, error code. |
| GET/DELETE | `/documents/{id}` | Inspect / delete (cascades chunks and file). |
| GET | `/documents/{id}/chunks` | Indexed chunks with page numbers. |
| GET | `/chunks/{id}` | Single chunk for citation preview. |
| POST | `/chat` | `{question, conversation_id?, top_k?}` → answer, citations, abstained, usage. |
| GET | `/conversations`, `/conversations/{id}/messages` | History. |
| POST/GET | `/incidents` | Create (log is sanitized before storage) / list. |
| GET/PATCH/DELETE | `/incidents/{id}` | Detail (includes latest analysis and RCA) / update / delete. |
| POST | `/incidents/{id}/analyze` | Structured analysis (§10 schema). |
| POST/GET/PATCH | `/incidents/{id}/rca` | Generate draft / read / edit. |
| POST | `/incidents/{id}/rca/confirm` | Requires `{"reviewer_acknowledgement": true}`. |
| GET | `/incidents/{id}/rca/export` | Markdown download. |
| GET | `/metrics/summary`, `/metrics/requests` | Ops metrics and recent traces. |

## Examples

```bash
TOKEN=$(curl -s localhost:8000/api/v1/auth/login -H 'content-type: application/json' \
  -d '{"email":"demo@resolveai.local","password":"<DEMO_USER_PASSWORD>"}' | jq -r .access_token)

curl -s localhost:8000/api/v1/documents -H "Authorization: Bearer $TOKEN" \
  -F file=@evals/fixtures/docs/nginx-502-runbook.md

curl -s localhost:8000/api/v1/chat -H "Authorization: Bearer $TOKEN" -H 'content-type: application/json' \
  -d '{"question":"What should I check first when Nginx returns 502?"}' | jq
```

Example chat response:

```json
{
  "conversation_id": "…",
  "answer": "Check whether the upstream service is running and listening on the proxy_pass port…",
  "citations": [{"chunk_id": "…", "document_id": "…", "filename": "nginx-502-runbook.md", "page": 1, "quote": "…"}],
  "abstained": false,
  "usage": {"provider": "openai", "model": "gpt-4o-mini", "input_tokens": 1520, "output_tokens": 190, "estimated_cost_usd": 0.00034},
  "request_id": "…"
}
```
