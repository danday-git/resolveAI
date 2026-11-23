# Security and threat model

ResolveAI is a portfolio demo, not a hardened production system. These are the controls it actually implements and the ones it deliberately leaves out.

## Trust boundaries

| Input | Treated as | Controls |
|---|---|---|
| Uploaded documents | Untrusted data | Extension + MIME + magic-byte sniffing, 10 MB limit, random storage names (no user path), encrypted/no-text PDFs rejected, chunks wrapped as `<chunk>` data in prompts. |
| Incident logs | Untrusted, possibly secret-bearing | Redacted before storage (API keys, bearer/JWT tokens, passwords in URLs/`key=value`, AWS keys, private keys, emails, public IPs). Raw log is never persisted or logged. |
| Model output | Untrusted | Parsed as JSON and validated; citations checked against stored chunk text; unknown chunk/evidence IDs dropped; destructive commands moved to safety warnings; hypotheses forced to `suspected`. |
| Users | Authenticated demo users | bcrypt hashes, signed JWT (bearer or HTTP-only `SameSite=Strict` cookie), owner filter on every query, 403 on cross-user access. |

## Prompt-injection defense

1. System prompts (`services/api/app/services/llm/prompts.py`) state that chunk/log content is data and cannot change instructions.
2. Retrieved text is escaped and wrapped in delimited blocks; chunks matching injection heuristics are flagged in the prompt.
3. The model never has tools, shell access, or network access. The only output channel is validated JSON.
4. Citations must quote text that exists in a retrieved chunk, so an injected "cite this fake ID" is dropped and the answer abstains.
5. The eval dataset has prompt-injection cases (`pi-*`) that are a release gate in CI.

## Safety rules

- No autonomous remediation: ResolveAI suggests read-only checks only and never executes commands.
- Root cause is never auto-confirmed. Confirmation requires an explicit human acknowledgement, a written confirmed cause and evidence; edits after confirmation reset it.
- Operational logs (`request_logs`, `llm_requests`, stdout JSON logs) store request IDs, routes, latency, provider/model, token counts and cost estimates — never prompts, document text, raw logs, tokens or API keys.

## Abuse limits

Per-user rate limit on LLM endpoints (`RATE_LIMIT_PER_MINUTE`), upload size cap, `top_k` bounded 1–10, context token budget, max output tokens, and a simulated daily budget alert.

## Out of scope (known limitations)

Real SSO/RBAC, multi-tenant isolation beyond `owner_id`, malware scanning of uploads, OCR, encryption at rest beyond what the database provides, and distributed rate limiting (the limiter is in-process).

## Secrets

Secrets come only from environment variables. `.env.example` holds placeholders, `.env` is git-ignored, and CI runs gitleaks. Test fixtures contain *synthetic* credentials on purpose to test redaction.
