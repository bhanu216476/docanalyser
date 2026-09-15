# Reranking Experiment Framework

**Day 11 — DocAnalyser RAG Service**

---

## 1. Purpose

Raw retrieval results (dense, BM25, or hybrid) rank documents by approximate
relevance signals. A **reranker** (cross-encoder, interaction model, or scoring
function) applies a more expensive but more precise relevance model to a small
set of top candidates.

The reranking experiment framework exists to make reranking **measurable**:

```
Query
  ↓
Dense Retrieval + BM25 Retrieval
  ↓
Reciprocal Rank Fusion (RRF)
  ↓
Hybrid Top-N candidates
  ↓
Reranker
  ↓
Final Ranking
  ↓
Experiment Metrics
```

Without measurement, a reranker is a black box. This framework captures:
- **Retrieval score** — pre-reranking relevance signal (RRF score)
- **Reranker score** — post-reranking relevance signal
- **Latency** — per-stage high-resolution timing
- **Ranking changes** — quantified displacement, overlap, and correlation

---

## 2. Architecture

```
┌──────────────────────────────────────────────────────────┐
│                  RerankedPipeline                        │
│                                                          │
│   Retriever.retrieve()  ──timedby──► retrieval_ms        │
│         │                                                │
│         ▼                                                │
│   candidate list                                         │
│         │                                                │
│   Reranker.rerank()     ──timedby──► reranking_ms        │
│         │                                                │
│         ▼                                                │
│   RerankedResult[]                                       │
│         │                                                │
│   compute_ranking_metrics()                              │
│         │                                                │
│         ▼                                                │
│   RerankExperimentResult                                 │
└──────────────────────────────────────────────────────────┘
```

**Module locations:**

| Component | Path |
|---|---|
| Reranker protocol | `app/reranking/base.py` |
| MockReranker | `app/reranking/mock_reranker.py` |
| Data models | `app/reranking/models.py` |
| Ranking metrics | `app/reranking/metrics.py` |
| Pipeline | `app/reranking/pipeline.py` |
| Experiment framework | `app/reranking/experiment.py` |

---

## 3. Score Preservation

> [!IMPORTANT]
> The retrieval score and reranker score are preserved on **separate fields**.
> The retrieval score is NEVER overwritten by the reranker score.

| Field | Contains | Scale |
|---|---|---|
| `retrieval_score` | Pre-reranking score (e.g. RRF score) | RRF: ~(0.01, 0.05) |
| `reranker_score` | Score assigned by the reranker | Reranker-specific |
| `retrieval_rank` | 1-based position before reranking | 1-indexed integer |
| `reranked_rank` | 1-based position after reranking | 1-indexed integer |
| `rank_delta` | `retrieval_rank - reranked_rank` | Signed integer |

**Example:**

```json
{
  "chunk_id": "chunk-A",
  "retrieval_score": 0.0321,
  "reranker_score": 0.91,
  "retrieval_rank": 3,
  "reranked_rank": 1,
  "rank_delta": 2
}
```

`rank_delta = 2` → document promoted by 2 positions.

---

## 4. Ranking Change Metrics

### Mean Rank Displacement

Average absolute change in position across all reranked documents:

```
MeanDisplacement = (1/N) * Σ |retrieval_rank_i - reranked_rank_i|
```

Lower displacement → reranker largely agrees with retrieval order.
Higher displacement → reranker substantially reorders candidates.

### Top-1 Changed

Boolean flag indicating whether the document ranked #1 before reranking
is still ranked #1 after reranking.

This is the most important practical signal — did the top answer change?

### Top-K Jaccard Overlap

Measures set overlap between the top-K documents before and after reranking:

```
JaccardOverlap(k) = |pre_top_k ∩ post_top_k| / |pre_top_k ∪ post_top_k|
```

- `1.0` — exactly the same documents in top-K.
- `0.0` — no overlap; completely different top-K set.

### Spearman Rank Correlation

Measures the correlation between pre- and post-reranking rank orderings for
all shared documents:

```
SpearmanR = Σ[(r_pre - mean_pre)(r_post - mean_post)] /
            sqrt(Σ(r_pre - mean_pre)² * Σ(r_post - mean_post)²)
```

- `1.0` — perfect rank agreement.
- `0.0` — no correlation.
- `-1.0` — perfectly inverted ranking.

### Promotion / Demotion Counts

- **Promoted** (`rank_delta > 0`): Chunk moved to a better position.
- **Demoted** (`rank_delta < 0`): Chunk moved to a worse position.
- **Unchanged** (`rank_delta == 0`): Position identical.

---

## 5. High-Resolution Latency Measurement

Latency is measured using `time.perf_counter()`, which provides
monotonic, high-resolution timing (typically sub-microsecond precision on
modern platforms). Wall-clock timing with `time.time()` is explicitly avoided
to prevent distortion from NTP adjustments or system clock changes.

```python
retrieval_start = time.perf_counter()
candidates = retriever.retrieve(query, top_k=candidate_k)
retrieval_latency_ms = (time.perf_counter() - retrieval_start) * 1000.0

reranking_start = time.perf_counter()
reranked = reranker.rerank(query, candidates, top_k=top_k)
reranking_latency_ms = (time.perf_counter() - reranking_start) * 1000.0
```

All latencies are reported in **milliseconds** to 4 decimal places.

---

## 6. Reranker Provider Abstraction

The `Reranker` structural protocol allows any implementation that provides
the correct method signature:

```python
@runtime_checkable
class Reranker(Protocol):
    def rerank(
        self,
        query: str,
        documents: Sequence[RetrievalResult],
        top_k: Optional[int] = None,
    ) -> list[RerankedResult]:
        ...
```

**Possible implementations:**

| Type | Description |
|---|---|
| `MockReranker` | Deterministic offline reranker for testing |
| Cross-encoder | Local transformer model (e.g. `cross-encoder/ms-marco-MiniLM-L-6-v2`) |
| External API | Remote reranking service (e.g. Cohere Rerank, Jina AI Rerank) |
| Learned sparse | BM25 re-implementation as a reranker |

No external API or GPU is required to run tests — all unit tests use
`MockReranker`.

---

## 7. MockReranker Scoring Logic

The `MockReranker` computes deterministic scores in `[0.0, 1.0]`:

```
score = min(1.0, 0.7 * token_overlap_ratio + phrase_bonus)
```

Where:
- `token_overlap_ratio = |query_tokens ∩ chunk_tokens| / |query_tokens|`
- `phrase_bonus = 0.3` if the full query string is contained verbatim in the chunk.

Custom scores can override the algorithm per chunk_id:

```python
reranker = MockReranker(custom_scores={"chunk-A": 0.95, "chunk-B": 0.15})
```

---

## 8. Example Usage

### Single Query Experiment

```python
from app.retrieval.hybrid_retriever import create_hybrid_retriever
from app.reranking.mock_reranker import MockReranker
from app.reranking.pipeline import RerankedPipeline
from app.reranking.experiment import RerankingExperimentFramework

pipeline = RerankedPipeline(
    retriever=create_hybrid_retriever(),
    reranker=MockReranker(),
    top_k=5,
    candidate_k=20,
)
framework = RerankingExperimentFramework(pipeline)

result = framework.run_single("What is the authentication policy?")
print(framework.format_single_report(result))
```

### Batch Experiment

```python
report = framework.run_batch([
    "authentication policy",
    "sick leave entitlement",
    "network security requirements",
])
print(framework.format_batch_report(report))
```

---

## 9. Deterministic Tie-Breaking in Reranking

When two candidates have equal reranker scores, the secondary sort key is
`chunk_id` (alphabetical ascending) — identical to the RRF layer's
tie-breaking logic. This guarantees reproducible results across repeated runs.

---

## 10. What This Framework Is NOT

> [!NOTE]
> This framework measures retrieval + reranking pipeline performance using
> **latency**, **score distributions**, and **ranking shift metrics**.
>
> It does NOT:
> - Generate LLM answers or citations.
> - Implement offline evaluation with ground-truth relevance labels (e.g. NDCG, MAP).
>   That requires a labelled test set and is a future evaluation layer.
> - Replace human judgment or end-to-end QA evaluation.
