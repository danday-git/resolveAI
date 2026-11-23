# ResolveAI evaluation report — multilingual.jsonl

- Generated: 2026-11-23T14:54:49+00:00 (git `7855451`)
- Chat provider/model: `ollama` / `llama3.2:3b`
- Embedding provider/model: `ollama` / `nomic-embed-text-v2-moe` (dim 768)
- Dataset: 20 items {'cross_lingual_en_to_id': 2, 'cross_lingual_id': 10, 'cross_lingual_other': 3, 'same_language_id': 2, 'unanswerable_id': 3}, top_k=5
- Environment: Linux x86_64, Python 3.12.16, in-process TestClient
- **Release gates: PASS**

| Metric | RAG |
|---|---|
| Recall@5 (expected chunk in top-5 retrieved) | 1.0 |
| Citation validity — shipped citations re-verified against stored text | 1.0 |
| Citation validity — model-proposed citations accepted by validator | 0.8667 |
| Abstention accuracy (unanswerable items that abstained) | 1.0 |
| False abstention rate (answerable items that abstained) | 0.2353 |
| Unsupported-claim rate (automated must_not_claim proxy) | 0.0 |
| must_include coverage (answered items) | 1.0 |
| Answered items citing an expected source | 1.0 |
| Latency p50 (ms, client-measured) | 12567.0 |
| Latency p95 (ms, client-measured) | 16571.2 |
| Failure rate (non-200) | 0.0 |
| Input tokens (total) | 30456 |
| Output tokens (total) | 1616 |
| Estimated cost USD (estimate, configurable pricing) | 0.0 |

## Per-scenario

| Scenario | Items | Abstained | must_not_claim violations |
|---|---|---|---|
| cross_lingual_en_to_id | 2 | 0 | 0 |
| cross_lingual_id | 10 | 4 | 0 |
| cross_lingual_other | 3 | 0 | 0 |
| same_language_id | 2 | 0 | 0 |
| unanswerable_id | 3 | 3 | 0 |

## Failures and notable items

- `id-kb-02` (cross_lingual_id): wrong abstention decision; missing ['ss -ltnp']
- `id-kb-09` (cross_lingual_id): wrong abstention decision; missing ['lsof +L1']
- `id-ts-02` (cross_lingual_id): wrong abstention decision; missing ['pg_stat_activity']
- `id-pi-02` (cross_lingual_id): wrong abstention decision; missing ['6379']

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
