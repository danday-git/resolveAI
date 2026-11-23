# ADR 0002: Multi-provider LLM abstraction

Status: Accepted (changes the PRD default of a single OpenAI provider)

## Context
The demo should run with a paid API (OpenAI, Anthropic) and with zero cost locally (Ollama), and tests must never call a real model. Chat and embeddings have different provider availability: Anthropic has no embeddings API.

## Decision
- Two interfaces in `services/api/app/services/llm/base.py`: `ChatProvider.chat(messages, json_mode, max_tokens, temperature) -> ChatResult` and `EmbeddingProvider.embed(texts) -> EmbeddingResult`. Results carry provider, model, token usage and latency.
- Adapters: `openai` (chat + embeddings), `anthropic` (chat only), `ollama` (chat + embeddings), `mock` (deterministic, used by tests and keyless demos). All use `httpx` with a shared timeout/retry helper (retry on 429/5xx/timeouts with backoff; no retry on 4xx auth errors).
- Chat and embeddings are configured separately: `LLM_PROVIDER`/`LLM_MODEL` and `EMBEDDING_PROVIDER`/`EMBEDDING_MODEL`/`EMBEDDING_DIM`. With `LLM_PROVIDER=anthropic` and no embedding provider set, embeddings default to OpenAI; explicitly setting `EMBEDDING_PROVIDER=anthropic` is a startup error.
- The vector column is `vector(EMBEDDING_DIM)`. On startup the API compares `EMBEDDING_DIM` with the known dimension of the configured embedding model and with the dimension of the existing `chunks.embedding` column, and refuses to start with a message explaining how to fix it (change the variable, or reset the database and re-ingest).
- Costs come from a pricing table (`pricing.py`) overridable with `LLM_PRICING_FILE` (JSON). Unknown models record `estimated_cost_usd = null` instead of guessing. Every call writes provider and exact model to `llm_requests`; eval reports record both chat and embedding provider/model.
- No code outside `app/services/llm/` knows which provider is active.

## Consequences
- Switching providers is an environment change; switching *embedding* model or dimension requires re-ingesting documents (embeddings from different models are not comparable).
- JSON output reliability varies by model: small local models (e.g. `qwen2.5:1.5b`) produce more invalid JSON or invalid citations, which the validators turn into abstentions. Quality numbers must always be read together with the provider/model in the report.
- Provider features beyond plain chat (tool calling, streaming) are not used, which keeps adapters small.
