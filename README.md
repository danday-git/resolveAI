# ResolveAI

AI incident investigation assistant for IT support and DevOps engineers. Upload runbooks and SOPs, ask grounded questions with verifiable citations, analyze incident logs into evidence-backed (but explicitly *suspected*) hypotheses, and produce RCA drafts that only a human can confirm.

Built as a portfolio project to show production-minded AI engineering: grounded RAG, server-side citation validation, prompt-injection defense, structured output validation, multi-provider LLM support, observability, offline evaluation and CI.

> All demo data is synthetic. ResolveAI never executes commands and never auto-confirms a root cause.

## Features

| Area | What it does |
|---|---|
| Knowledge Base | Upload PDF/TXT/MD (≤ 10 MB). Text extraction with page numbers, page-aware chunking with overlap, duplicate detection, embeddings in pgvector. Encrypted and scanned PDFs are rejected with a clear error. |
| Assistant | Owner-filtered top-k retrieval, grounded answers with `{chunk_id, quote}` citations validated against stored text, abstention when evidence is missing, click-to-preview exact source excerpt. |
| Incidents | Incident records with secret redaction before storage, deterministic log observations with line numbers, structured analysis (observations, suspected hypotheses, read-only verification steps, missing information, safety warnings). |
| RCA | Draft generator (always `UNCONFIRMED`), editor, explicit human confirmation with reviewer + timestamp, Markdown export. |
| Ops | Structured JSON request logs (no prompts or secrets), request IDs, latency, tokens and estimated cost per provider/model, `/metrics/summary`, simulated alert thresholds. |
| Evaluation | 30-case dataset (KB, troubleshooting, unanswerable, conflicting docs, prompt injection), CLI runner with Recall@5, citation validity, abstention accuracy, unsupported-claim rate, latency, cost, and a no-retrieval baseline. |

## Architecture

```mermaid
flowchart LR
  B[Browser] --> W[Next.js apps/web] -->|/api rewrite| A[FastAPI services/api]
  A --> D[(PostgreSQL 16 + pgvector)]
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
| Anthropic chat + local embeddings | `LLM_PROVIDER=anthropic` `ANTHROPIC_API_KEY=…` `EMBEDDING_PROVIDER=ollama` `EMBEDDING_MODEL=nomic-embed-text` `EMBEDDING_DIM=768` |
| Ollama (free, local) | `LLM_PROVIDER=ollama` `LLM_MODEL=qwen2.5:1.5b` `EMBEDDING_PROVIDER=ollama` `EMBEDDING_MODEL=nomic-embed-text` `EMBEDDING_DIM=768` `OLLAMA_BASE_URL=http://ollama:11434` |
| Mock (no network) | `LLM_PROVIDER=mock` `EMBEDDING_PROVIDER=mock` `EMBEDDING_DIM=256` |

**Anthropic has no embeddings API.** If `LLM_PROVIDER=anthropic` and `EMBEDDING_PROVIDER` is unset, embeddings default to OpenAI (needs `OPENAI_API_KEY`); setting `EMBEDDING_PROVIDER=anthropic` is a startup error.

Ollama runs as an optional Compose profile:

```bash
docker compose -f infra/docker-compose.yml --env-file .env --profile web --profile ollama up --build -d
docker compose -f infra/docker-compose.yml exec ollama ollama pull qwen2.5:1.5b
docker compose -f infra/docker-compose.yml exec ollama ollama pull nomic-embed-text
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

## Limitations

- Demo authentication only (single seeded user, JWT); no SSO, RBAC or multi-tenant isolation beyond per-user ownership.
- Ingestion runs as an in-process background task: a restart mid-ingestion leaves the document in `processing`; re-upload it.
- No OCR: scanned PDFs are rejected. No malware scanning of uploads.
- Rate limiting is in-process (single API instance).
- The mock provider is extractive and deterministic — useful for tests and keyless demos, not a quality benchmark. Small local models produce more invalid JSON/citations, which the validators turn into abstentions.
- Unsupported-claim rate in evals is a heuristic (forbidden-claim phrases + citation checks), not human judgement.
- ResolveAI never executes commands and never auto-remediates. Suggested checks are read-only and must be run by an engineer.

## License

MIT — see [LICENSE](LICENSE).
