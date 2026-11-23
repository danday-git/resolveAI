# ResolveAI

AI incident investigation assistant for IT support and DevOps engineers. Upload runbooks and SOPs, ask grounded questions with verifiable citations, analyze incident logs into evidence-backed (but explicitly *suspected*) hypotheses, and produce RCA drafts that only a human can confirm.

Built as a portfolio project to show production-minded AI engineering: grounded RAG, server-side citation validation, prompt-injection defense, structured output validation, multi-provider LLM support, observability, offline evaluation and CI.

> All demo data is synthetic. ResolveAI never executes commands and never auto-confirms a root cause.

![The Assistant answering an Indonesian question from an English runbook, with the cited excerpt open](docs/screenshots/assistant.png)

| Knowledge Base | Incident analysis | RCA draft (UNCONFIRMED) |
|---|---|---|
| ![Indexed runbooks and SOPs](docs/screenshots/knowledge.png) | ![Observations, possible causes and read-only checks](docs/screenshots/analysis.png) | ![An RCA draft waiting for a reviewer](docs/screenshots/rca.png) |

Screens are from a local run with Ollama (`llama3.2:3b`, `nomic-embed-text-v2-moe`). A 36-second [screen recording](site/demo.mp4) shows the whole flow. A static showcase page lives in [`site/`](site/index.html) and deploys to GitHub Pages with the `pages` workflow.

## Features

| Area | What it does |
|---|---|
| Knowledge Base | Upload PDF/TXT/MD (≤ 10 MB). Text extraction with page numbers, page-aware chunking with overlap, duplicate detection, embeddings in pgvector. Encrypted PDFs are rejected with a clear error; scanned pages are read with OCR. |
| Assistant | Owner-filtered top-k retrieval, grounded answers with `{chunk_id, quote}` citations validated against stored text, abstention when evidence is missing, click-to-preview exact source excerpt. |
| Incidents | Incident records with secret redaction before storage, deterministic log observations with line numbers, structured analysis (observations, suspected hypotheses, read-only verification steps, missing information, safety warnings). |
| RCA | Draft generator (always `UNCONFIRMED`), editor, explicit human confirmation with reviewer + timestamp, Markdown export. |
| Ops | Structured JSON request logs (no prompts or secrets), request IDs, latency, tokens and estimated cost per provider/model, `/metrics/summary`, simulated alert thresholds. |
| Evaluation | 30-case dataset (KB, troubleshooting, unanswerable, conflicting docs, prompt injection), CLI runner with Recall@5, citation validity, abstention accuracy, unsupported-claim rate, latency, cost, and a no-retrieval baseline. |

## Accounts, operations and data controls

| Area | What it does |
|---|---|
| Accounts | Registration (`ALLOW_REGISTRATION`), `admin` and `member` roles, password change and reset, optional OIDC single sign-on, admin page for users and the audit log. Administrators manage accounts; they do not see other users' documents or incidents. |
| Ingestion worker | Documents are queued in PostgreSQL and indexed by a separate `worker` service with retry and backoff. Documents left in `processing` by a crash are picked up again. |
| Scale | Rate limits are counted in PostgreSQL, so they hold across API instances. Incident and document lists are searched, filtered and paged on the server. |
| Uploads | Optional ClamAV scan before a file is stored (Compose profile `scan`, fails closed) and Tesseract OCR for PDF pages without a text layer. |
| Operations | Caddy HTTPS overlay, backup and restore scripts, a token-protected Prometheus endpoint and optional Sentry. See the [deployment guide](docs/deployment.md). |
| Data controls | Audit events for account, document, incident and RCA changes; `RETENTION_*_DAYS` cleanup; per-user consent before any data is sent to OpenAI or Anthropic (not needed for Ollama or mock). |

## Architecture

```mermaid
flowchart LR
  B[Browser] --> W[Next.js apps/web] -->|/api rewrite| A[FastAPI services/api]
  A --> D[(PostgreSQL 16 + pgvector)]
  K[Ingestion worker] --> D
  A --> L{{OpenAI / Anthropic / Ollama / mock}}
```

Details: [architecture](docs/architecture/overview.md) · [API](docs/api/README.md) · [security](docs/security/README.md) · [ADRs](docs/decisions/) · [demo script](docs/demo/script.md)

```
apps/web/                 Next.js + TypeScript + Tailwind
services/api/app/api      FastAPI routes
services/api/app/core     config, auth, db, redaction, logging
services/api/app/models   SQLAlchemy models
services/api/app/services ingestion · retrieval · llm · incidents · rca
services/api/alembic/     migrations
services/api/tests/       unit · integration (incl. E2E flow)
evals/                    datasets · fixtures · reports · run_eval.py
infra/docker-compose.yml
```

## Quick start (Docker)

Requirements: Docker with Compose v2.

```bash
cp .env.example .env
# edit .env: set JWT_SECRET (32+ random chars), DEMO_USER_PASSWORD, and a provider (see below)

docker compose -f infra/docker-compose.yml --env-file .env --profile web up --build -d
docker compose -f infra/docker-compose.yml exec api python -m app.seed --with-fixtures
```

- Web: http://localhost:3000 — log in with `demo@resolveai.local` / the `DEMO_USER_PASSWORD` you set.
- API docs: http://localhost:8000/docs · health: `/health` · readiness: `/ready`
- Postgres is exposed on host port 5433.

No API key? Use the keyless mock provider (deterministic, extractive answers) or Ollama, below.

## Choosing an LLM provider

Chat and embeddings are configured independently. Changing the **embedding** model or dimension requires a fresh database (`docker compose ... down -v`) and re-ingestion, because vectors from different models are not comparable. The API refuses to start if `EMBEDDING_DIM` does not match the model or the existing schema.

| Setup | `.env` |
|---|---|
| OpenAI (default) | `LLM_PROVIDER=openai` `EMBEDDING_PROVIDER=openai` `OPENAI_API_KEY=sk-…` `EMBEDDING_MODEL=text-embedding-3-small` `EMBEDDING_DIM=1536` |
| Anthropic chat + OpenAI embeddings | `LLM_PROVIDER=anthropic` `LLM_MODEL=claude-haiku-4-5` `ANTHROPIC_API_KEY=…` `EMBEDDING_PROVIDER=openai` `OPENAI_API_KEY=…` `EMBEDDING_DIM=1536` |
| Anthropic chat + local embeddings | `LLM_PROVIDER=anthropic` `ANTHROPIC_API_KEY=…` `EMBEDDING_PROVIDER=ollama` `EMBEDDING_MODEL=nomic-embed-text-v2-moe` `EMBEDDING_DIM=768` |
| Ollama (free, local) | `LLM_PROVIDER=ollama` `LLM_MODEL=llama3.2:3b` `EMBEDDING_PROVIDER=ollama` `EMBEDDING_MODEL=nomic-embed-text-v2-moe` `EMBEDDING_DIM=768` `OLLAMA_BASE_URL=http://ollama:11434` |
| Mock (no network) | `LLM_PROVIDER=mock` `EMBEDDING_PROVIDER=mock` `EMBEDDING_DIM=256` |

**Anthropic has no embeddings API.** If `LLM_PROVIDER=anthropic` and `EMBEDDING_PROVIDER` is unset, embeddings default to OpenAI (needs `OPENAI_API_KEY`); setting `EMBEDDING_PROVIDER=anthropic` is a startup error.

**Changing the chat model without a restart.** Administrators can open **AI provider** in the sidebar to pick the chat provider and model, paste an OpenAI or Anthropic API key, and run **Test connection**. The choice applies to every account and overrides `LLM_PROVIDER`, `LLM_MODEL` and the API key variables for chat. Keys are stored encrypted with a key derived from `JWT_SECRET` and are never shown again (only the last 4 characters); rotating `JWT_SECRET` makes saved keys unreadable, so enter them again afterwards. Switching to OpenAI or Anthropic asks every user for consent again. The embedding model is shown but stays in `.env`, because changing it needs re-ingestion. Embeddings keep using the key from `.env`.

Ollama runs as an optional Compose profile:

```bash
docker compose -f infra/docker-compose.yml --env-file .env --profile web --profile ollama up --build -d
docker compose -f infra/docker-compose.yml exec ollama ollama pull llama3.2:3b
docker compose -f infra/docker-compose.yml exec ollama ollama pull nomic-embed-text-v2-moe
```

Costs are estimates from the pricing table in `services/api/app/services/llm/pricing.py`; override with `LLM_PRICING_FILE=/path/prices.json` (`{"provider:model": {"input_per_1m": 0.15, "output_per_1m": 0.6}}`). Unknown models record a `null` cost instead of a guess. Every LLM call stores provider and exact model in `llm_requests`.

## Local development

```bash
# database only
docker compose -f infra/docker-compose.yml --env-file .env up -d db

# API (Python 3.12, uv)
cd services/api
uv sync
uv run alembic upgrade head
uv run python -m app.seed --with-fixtures
uv run uvicorn app.main:app --reload

# web (Node 22)
cd apps/web
npm ci
npm run dev          # http://localhost:3000, proxies /api to http://localhost:8000
```

For local runs set `UPLOAD_DIR=./uploads` in `.env` (the default `/data/uploads` is the container path).

## API example

```bash
TOKEN=$(curl -s localhost:8000/api/v1/auth/login -H 'content-type: application/json' \
  -d '{"email":"demo@resolveai.local","password":"<DEMO_USER_PASSWORD>"}' | jq -r .access_token)
curl -s localhost:8000/api/v1/chat -H "Authorization: Bearer $TOKEN" -H 'content-type: application/json' \
  -d '{"question":"What should I check first when Nginx returns 502?"}' | jq
```

More in [docs/api](docs/api/README.md).

## Tests and quality gates

```bash
cd services/api
docker compose -f ../../infra/docker-compose.yml --env-file ../../.env up -d db
docker compose -f ../../infra/docker-compose.yml exec db createdb -U resolveai resolveai_test
uv run ruff check . && uv run ruff format --check . && uv run mypy app
uv run pytest -q                       # unit + integration + E2E; all LLM calls mocked

cd ../../apps/web && npm run lint && npm run typecheck && npm run build
```

Integration tests use `TEST_DATABASE_URL` (default `postgresql+psycopg://resolveai:resolveai@localhost:5433/resolveai_test`). CI (`.github/workflows/ci.yml`) runs lint, typecheck, all tests against pgvector, the mock evaluation with release gates, gitleaks, `pip-audit` and `npm audit`.

## Evaluation

```bash
cd services/api
# in-process against the configured providers (uses DATABASE_URL); add --baseline for the no-retrieval comparison
uv run python ../../evals/run_eval.py --baseline
# or against a running API
uv run python ../../evals/run_eval.py --base-url http://localhost:8000 --email demo@resolveai.local --password '<pw>'
```

Reports are written to `evals/reports/<name>.json` and `.md`, with chat and embedding provider/model, Recall@5, citation validity, abstention accuracy, unsupported-claim rate, p50/p95 latency, failure rate, tokens and estimated cost per scenario type. The run fails if any shipped citation is invalid or a prompt-injection case produces unsafe output.

Committed reports are in [`evals/reports/`](evals/reports/). Scores depend heavily on the model: read every number together with the provider/model it was produced by.

Results on the 30-case dataset with free local models (Ollama on an 8-core CPU, no GPU, `nomic-embed-text` embeddings, top-5 retrieval). The mock row is a deterministic extractive stub, not a language model; it is listed only to show that the pipeline numbers are not model quality.

| Metric | `llama3.2:3b` | `qwen2.5:1.5b` | mock |
|---|---|---|---|
| Recall@5 | 1.00 | 1.00 | 0.80 |
| Shipped citations valid | 1.00 | 1.00 | 1.00 |
| Model-proposed citations accepted | 0.74 | 0.75 | 1.00 |
| Unanswerable questions that abstained | 5 of 5 | 2 of 5 (2 more failed) | 5 of 5 |
| Answerable questions wrongly abstained | 0.28 | 0.17 | 0.24 |
| Unsupported-claim rate (heuristic) | 0.00 | 0.12 | 0.07 |
| Required facts present in answers | 0.72 | 0.79 | 0.63 |
| Requests failed (invalid model output) | 0 of 30 | 4 of 30 | 0 of 30 |
| Latency p50 / p95 | 15.5 s / 23.9 s | 12.3 s / 26.4 s | 0.02 s |
| Release gates | pass | pass | pass |

Reading: every citation that reaches the user is valid with both models, because the server drops the roughly one in four citations the models get wrong. `llama3.2:3b` is the safer choice: no failed requests and no unsupported claims, but it declines about a quarter of answerable questions. `qwen2.5:1.5b` answers more, fails on 4 of 30 requests, and the heuristic flags its answer in 3 of 4 conflicting-document cases for containing the outdated value. Thirty cases is a small sample, and no hosted model (OpenAI, Anthropic) has been evaluated.

### Multilingual questions

The Assistant answers in the language of the question and quotes sources verbatim in their own language, so an Indonesian question can be answered from an English runbook and the other way round. Cross-language retrieval needs a multilingual embedding model; the local default is `nomic-embed-text-v2-moe`. Switching from `nomic-embed-text` keeps `EMBEDDING_DIM=768` but still needs a fresh database and re-ingestion, because vectors from different models are not comparable.

`llama3.2:3b` with `nomic-embed-text-v2-moe` ([`evals/datasets/multilingual.jsonl`](evals/datasets/multilingual.jsonl), 20 cases in Indonesian, Spanish, German, Japanese and English, including an Indonesian SOP):

| Metric | Multilingual (20) | English v1 (30), v2-moe | English v1 (30), nomic-embed-text |
|---|---|---|---|
| Recall@5 | 1.00 | 1.00 | 1.00 |
| Shipped citations valid | 1.00 | 1.00 | 1.00 |
| Unanswerable questions that abstained | 3 of 3 | 5 of 5 | 5 of 5 |
| Answerable questions wrongly abstained | 0.24 | 0.20 | 0.28 |
| Unsupported-claim rate (heuristic) | 0.00 | 0.03 | 0.00 |
| Required facts present in answers | 1.00 | 0.85 | 0.72 |
| Latency p50 | 12.6 s | 14.0 s | 15.5 s |

Reading: all 4 wrong abstentions are Indonesian questions about English runbooks, where retrieval found the right chunk but the 3B model declined. The English unsupported claim is one conflicting-document case (`cf-04`) where the model gave the outdated value. In a direct comparison of whole documents, the previous `nomic-embed-text` ranked the right English runbook first for 2 of 10 Indonesian questions; `nomic-embed-text-v2-moe` did for 10 of 10.

## Limitations

- Data is owned per user. There are no shared team workspaces, so an administrator cannot read or hand over another user's documents and incidents.
- OIDC sign-on was tested against a stub identity provider only, and password-reset email against no real SMTP server.
- One host and one database: no replication or failover. Backups are local files; copy them off the host yourself.
- OCR reads the first `OCR_MAX_PAGES` (50) scanned pages of a document and was tested on clean printed text only.
- Prometheus request counters are per API process; scrape every replica.
- Small local models take 12 to 25 seconds per answer on CPU, and the smallest one fails the structured-output check on some requests (see the evaluation table).
- The mock provider is extractive and deterministic — useful for tests and keyless demos, not a quality benchmark. Small local models produce more invalid JSON/citations, which the validators turn into abstentions.
- Unsupported-claim rate in evals is a heuristic (forbidden-claim phrases + citation checks), not human judgement.
- The fixed decline message ("I don't have enough evidence...") is in English whatever the question language, and small local models sometimes answer in English or mix languages.
- ResolveAI never executes commands and never auto-remediates. Suggested checks are read-only and must be run by an engineer.

## License

MIT — see [LICENSE](LICENSE).
