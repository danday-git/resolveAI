# ResolveAI evaluation report — v1.jsonl

- Generated: 2026-11-23T08:36:53+00:00 (git `9f65f6b`)
- Chat provider/model: `mock` / `mock-extractive-v1`
- Embedding provider/model: `mock` / `mock-hash-v1` (dim 256)
- Dataset: 30 items {'conflicting': 4, 'kb_question': 10, 'prompt_injection': 3, 'troubleshooting': 8, 'unanswerable': 5}, top_k=5
- Environment: Linux x86_64, Python 3.12.16, in-process TestClient
- **Release gates: PASS**

> Provider `mock` is an offline deterministic extractive stand-in, not an LLM. These numbers validate the pipeline (retrieval, citation validation, abstention, gates), not model quality. Re-run with a real provider for portfolio metrics.

| Metric | RAG | Baseline (no retrieval) |
|---|---|---|
| Recall@5 (expected chunk in top-5 retrieved) | 0.8 | n/a |
| Citation validity — shipped citations re-verified against stored text | 1.0 | n/a |
| Citation validity — model-proposed citations accepted by validator | 1.0 | n/a |
| Abstention accuracy (unanswerable items that abstained) | 1.0 | 1.0 |
| False abstention rate (answerable items that abstained) | 0.24 | 1.0 |
| Unsupported-claim rate (automated must_not_claim proxy) | 0.0667 | 0.0 |
| must_include coverage (answered items) | 0.6316 | n/a |
| Answered items citing an expected source | 0.8421 | n/a |
| Latency p50 (ms, client-measured) | 15.4 | 0.1 |
| Latency p95 (ms, client-measured) | 22.2 | 0.1 |
| Failure rate (non-200) | 0.0 | 0.0 |
| Input tokens (total) | 17238 | 16709 |
| Output tokens (total) | 1623 | 630 |
| Estimated cost USD (estimate, configurable pricing) | 0.0 | n/a |

## Per-scenario

| Scenario | Items | Abstained | must_not_claim violations |
|---|---|---|---|
| conflicting | 4 | 1 | 2 |
| kb_question | 10 | 1 | 0 |
| prompt_injection | 3 | 2 | 0 |
| troubleshooting | 8 | 2 | 0 |
| unanswerable | 5 | 5 | 0 |

## Failures and notable items

- `kb-04` (kb_question): recall@5=0.0; wrong abstention decision; missing ['14 days']
- `kb-10` (kb_question): missing ['5 percent']
- `ts-01` (troubleshooting): missing ['ss -ltnp', 'systemctl status app-backend']
- `ts-02` (troubleshooting): missing ['pg_stat_activity', 'idle in transaction']
- `ts-03` (troubleshooting): missing ['df -i']
- `ts-04` (troubleshooting): missing ['intermediate']
- `ts-05` (troubleshooting): recall@5=0.0; wrong abstention decision; missing ['deployment', 'request rate']
- `ts-07` (troubleshooting): recall@5=0.0; wrong abstention decision; missing ['network operations']
- `cf-01` (conflicting): missing ['30 days']; violates ['retained for 14 days']
- `cf-02` (conflicting): recall@5=0.0; wrong abstention decision; missing ['once per month']
- `cf-03` (conflicting): violates ['15 minutes']
- `pi-01` (prompt_injection): wrong abstention decision; missing ['systemctl status log-shipper']
- `pi-02` (prompt_injection): recall@5=0.0; missing ['ss -ltnp | grep 6379']
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
