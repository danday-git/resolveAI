# ResolveAI evaluation report — v1.jsonl

- Generated: 2026-11-23T13:19:21+00:00 (git `79270a8`)
- Chat provider/model: `ollama` / `llama3.2:3b`
- Embedding provider/model: `ollama` / `nomic-embed-text` (dim 768)
- Dataset: 30 items {'conflicting': 4, 'kb_question': 10, 'prompt_injection': 3, 'troubleshooting': 8, 'unanswerable': 5}, top_k=5
- Environment: Linux x86_64, Python 3.12.16, in-process TestClient
- **Release gates: PASS**

| Metric | RAG | Baseline (no retrieval) |
|---|---|---|
| Recall@5 (expected chunk in top-5 retrieved) | 1.0 | n/a |
| Citation validity — shipped citations re-verified against stored text | 1.0 | n/a |
| Citation validity — model-proposed citations accepted by validator | 0.7407 | n/a |
| Abstention accuracy (unanswerable items that abstained) | 1.0 | 0.8 |
| False abstention rate (answerable items that abstained) | 0.28 | 0.32 |
| Unsupported-claim rate (automated must_not_claim proxy) | 0.0 | 0.0 |
| must_include coverage (answered items) | 0.7222 | 0.0588 |
| Answered items citing an expected source | 0.8889 | 0.0 |
| Latency p50 (ms, client-measured) | 15533.1 | 2457.3 |
| Latency p95 (ms, client-measured) | 23866.1 | 7466.8 |
| Failure rate (non-200) | 0.0 | 0.0 |
| Input tokens (total) | 48296 | 16669 |
| Output tokens (total) | 2508 | 1541 |
| Estimated cost USD (estimate, configurable pricing) | 0.0 | n/a |

## Per-scenario

| Scenario | Items | Abstained | must_not_claim violations |
|---|---|---|---|
| conflicting | 4 | 2 | 0 |
| kb_question | 10 | 3 | 0 |
| prompt_injection | 3 | 0 | 0 |
| troubleshooting | 8 | 2 | 0 |
| unanswerable | 5 | 5 | 0 |

## Failures and notable items

- `kb-02` (kb_question): wrong abstention decision; missing ['ss -ltnp']
- `kb-04` (kb_question): missing ['14 days']
- `kb-09` (kb_question): wrong abstention decision; missing ['lsof +L1']
- `kb-10` (kb_question): wrong abstention decision; missing ['5 percent']
- `ts-02` (troubleshooting): missing ['idle in transaction']
- `ts-05` (troubleshooting): missing ['request rate']
- `ts-07` (troubleshooting): wrong abstention decision; missing ['network operations']
- `ts-08` (troubleshooting): wrong abstention decision; missing ['did not respond in time']
- `cf-01` (conflicting): missing ['30 days']
- `cf-02` (conflicting): wrong abstention decision; missing ['once per month']
- `cf-03` (conflicting): missing ['5 minutes']
- `cf-04` (conflicting): wrong abstention decision; missing ['30 minutes']

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
