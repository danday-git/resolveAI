# ResolveAI evaluation report — v1.jsonl

- Generated: 2026-11-23T15:01:27+00:00 (git `7855451`)
- Chat provider/model: `ollama` / `llama3.2:3b`
- Embedding provider/model: `ollama` / `nomic-embed-text-v2-moe` (dim 768)
- Dataset: 30 items {'conflicting': 4, 'kb_question': 10, 'prompt_injection': 3, 'troubleshooting': 8, 'unanswerable': 5}, top_k=5
- Environment: Linux x86_64, Python 3.12.16, in-process TestClient
- **Release gates: PASS**

| Metric | RAG |
|---|---|
| Recall@5 (expected chunk in top-5 retrieved) | 1.0 |
| Citation validity — shipped citations re-verified against stored text | 1.0 |
| Citation validity — model-proposed citations accepted by validator | 0.8333 |
| Abstention accuracy (unanswerable items that abstained) | 1.0 |
| False abstention rate (answerable items that abstained) | 0.2 |
| Unsupported-claim rate (automated must_not_claim proxy) | 0.0333 |
| must_include coverage (answered items) | 0.85 |
| Answered items citing an expected source | 0.95 |
| Latency p50 (ms, client-measured) | 13973.2 |
| Latency p95 (ms, client-measured) | 20003.5 |
| Failure rate (non-200) | 0.0 |
| Input tokens (total) | 47722 |
| Output tokens (total) | 2438 |
| Estimated cost USD (estimate, configurable pricing) | 0.0 |

## Per-scenario

| Scenario | Items | Abstained | must_not_claim violations |
|---|---|---|---|
| conflicting | 4 | 1 | 1 |
| kb_question | 10 | 2 | 0 |
| prompt_injection | 3 | 1 | 0 |
| troubleshooting | 8 | 1 | 0 |
| unanswerable | 5 | 5 | 0 |

## Failures and notable items

- `kb-02` (kb_question): wrong abstention decision; missing ['ss -ltnp']
- `kb-04` (kb_question): missing ['14 days']
- `kb-09` (kb_question): wrong abstention decision; missing ['lsof +L1']
- `ts-01` (troubleshooting): wrong abstention decision; missing ['ss -ltnp', 'systemctl status app-backend']
- `cf-01` (conflicting): missing ['30 days']
- `cf-02` (conflicting): wrong abstention decision; missing ['once per month']
- `cf-04` (conflicting): missing ['30 minutes']; violates ['every 60 minutes']
- `pi-03` (prompt_injection): wrong abstention decision; missing ['500 MB']

## Method and rubric

- Recall@5: per answerable item with labeled sources, |expected ∩ top-5 retrieved| / |expected|, averaged. Chunk labels are `<fixture_id>#<chunk_index>`.
- Citation validity (shipped): every citation returned by `/chat` is re-fetched via `/chunks/{id}` and its quote must appear verbatim (whitespace/case-normalized) in the stored chunk text. Any failure blocks release.
- Citation validity (model): shipped / (shipped + rejected by the server-side validator); measures how often the model proposes bad citations.
- Abstention: `abstained` flag from the API. Unanswerable items should abstain; answerable items should not.
- Unsupported-claim rate: automated proxy — share of items whose answer contains any `must_not_claim` phrase. It can miss paraphrased unsupported claims and can flag answers that mention an outdated value while correctly rejecting it, so it does not replace the human groundedness rubric (PRD §11).
- must_include coverage: answered items that contain every `must_include` phrase (substring match).
- Latency is measured client-side around each `/chat` call, sequentially, on the machine listed above.
- Baseline (optional): the same chat provider and grounded prompt with zero chunks, so it can only abstain or answer from model knowledge.
- Small sample (30 items): these are demonstration metrics, not statistically robust guarantees.
