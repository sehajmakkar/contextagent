# Retrieval eval: 2026-10-25

Memory set: 45 memories (1 folded as duplicates) extracted by `gemini-3.5-flash-lite` from 2 synthetic fixture weeks. Embeddings: `gemini-embedding-2` @ 768 dims.
Queries: 32 labelled, **31 answerable** (1 extraction miss(es): the source produced no memory).

| Mode | Recall@1 | Recall@5 | MRR@10 | p50 search | p95 search |
|---|---|---|---|---|---|
| bm25 | 84% (26/31) | 97% | 0.884 | 0.2 ms | 0.4 ms |
| vector | 90% (28/31) | 100% | 0.946 | 0.6 ms | 2.0 ms |
| hybrid | 90% (28/31) | 97% | 0.941 | 0.6 ms | 0.8 ms |
| hybrid_recency | 81% (25/31) | 97% | 0.879 | 0.6 ms | 0.7 ms |

Query embedding (network, uncached): 32 call(s), p50 605 ms, max 746 ms.
Search latency is local only: query vectors are cached before timing.

## Misses (not in the top 5)
- **bm25**: Who wants the cohort chart on slide 4?
- **vector**: none
- **hybrid**: Who wants the cohort chart on slide 4?
- **hybrid_recency**: Who wants the cohort chart on slide 4?

## Extraction misses
- What book did Ananya recommend?
