# Reciprocal Rank Fusion (RRF)

**Day 10 — DocAnalyser RAG Service**

---

## 1. Why Raw Dense and BM25 Scores Cannot Simply Be Added

Dense vector retrieval and BM25 keyword retrieval produce scores in completely
incompatible scales and distributions:

| Property | Dense (Cosine) | BM25 |
|---|---|---|
| Range | [−1.0, 1.0] | [0, ∞) (unbounded) |
| Distribution | Typically [0.75, 0.98] in practice | Depends on corpus size and query length |
| Semantic | Vector similarity | Lexical term frequency |

**Example:**

```
Dense scores:
    Document A → 0.91
    Document B → 0.87
    Document C → 0.82

BM25 scores:
    Document C → 8.42
    Document A → 6.71
    Document D → 5.98
```

Naively adding these scores gives:

- Document A: 0.91 + 6.71 = 7.62
- Document C: 0.82 + 8.42 = 9.24 (wins despite being #3 in dense)

The BM25 scale completely dominates the dense scale, making the "fusion"
meaningless. Score normalization (e.g. min-max) partially mitigates this but
is sensitive to outliers and corpus distribution shifts.

**RRF solves this problem by using rank positions instead of raw scores.**

---

## 2. RRF Concept and Formula

Reciprocal Rank Fusion (Cormack et al., 2009) assigns each document a fused
score based on its position (rank) across multiple retrieval systems:

```
RRF(d) = Σ_i  [ 1 / (k + r_i(d)) ]
```

Where:

- `d` — document or chunk
- `r_i(d)` — **1-based rank** of document `d` in retrieval system `i`
- `k` — smoothing constant (`k > 0`, default: 60)
- The sum is over all retrieval systems `i` in which `d` appears

**Key insight:** This converts incompatible scores into commensurable
reciprocal rank contributions. Rank 1 in any system contributes `1/(k+1)`,
regardless of whether the underlying score was 0.95 cosine or 42.7 BM25.

---

## 3. Rank Handling Rules

### 1-Based Ranks

Ranks are **1-based**: the top document has rank 1, not rank 0.

```
Dense results:
    chunk-A → rank 1
    chunk-B → rank 2
    chunk-C → rank 3
```

The formula uses `k + r_i(d)`. With 1-based ranks at `k=60`:
- Rank 1 → contributes `1/61 ≈ 0.01639`
- Rank 2 → contributes `1/62 ≈ 0.01613`

> [!CAUTION]
> Using 0-based ranks accidentally would cause rank 0 to contribute `1/k = 1/60 ≈ 0.01667`,
> which is *greater* than rank 1's `1/61 ≈ 0.01639`. This inverts the intended scoring.

### Missing Document Behavior

If a document does not appear in a particular retrieval list, it contributes
**exactly 0.0** from that list. There is no artificial low-rank penalty.

```python
# If chunk-X is only in Dense at rank 3 (not in BM25):
RRF(chunk-X) = 1 / (60 + 3) + 0.0 = 1/63 ≈ 0.015873
```

This is correct — absent documents receive no contribution, not a penalty.

### Per-Source Deduplication

If a chunk_id appears more than once within a single retrieval list (e.g. due
to upstream bugs), only its first/best (lowest 1-based rank) occurrence is
used. It receives exactly one contribution per retrieval system.

---

## 4. The Smoothing Constant k

### Effect of k

The smoothing constant `k` controls how quickly rank-based scores decay:

- **Small k** (e.g. `k=20`): The score difference between rank 1 and rank 5 is
  large. High-ranked documents dominate fusion.
- **Large k** (e.g. `k=100`): The score difference between ranks is compressed.
  Lower-ranked documents matter relatively more.

```
Rank 1 contribution:

k=20:   1/(20+1) = 1/21  ≈ 0.04762
k=60:   1/(60+1) = 1/61  ≈ 0.01639
k=100:  1/(100+1) = 1/101 ≈ 0.00990
```

### k-Experiment: k ∈ {20, 40, 60, 100}

Using the example input:
```
Dense:  A → rank 1, B → rank 2, C → rank 3
BM25:   C → rank 1, A → rank 2, D → rank 3
```

**Scores per k value:**

| Chunk | k=20   | k=40   | k=60   | k=100  |
|-------|--------|--------|--------|--------|
| A     | 0.08976| 0.04762| 0.03252| 0.01970|
| B     | 0.04545| 0.02381| 0.01613| 0.00980|
| C     | 0.08550| 0.04592| 0.03227| 0.01961|
| D     | 0.04348| 0.02273| 0.01587| 0.00971|

**Observations:**

1. **Ordering is stable across k values** for this example: A > C > B > D holds
   for all k ∈ {20, 40, 60, 100}. The ordering is not always k-invariant;
   it depends on rank positions across the two lists.

2. **Score compression increases with k**: At k=20, score span is `0.04628`.
   At k=100, score span is `0.00999`. Higher k reduces discrimination power
   between documents.

3. **k primarily affects sensitivity to high-ranked documents**: At k=20,
   rank 1 contributes `1/21 ≈ 0.0476`, while rank 4 contributes `1/24 ≈ 0.0417`
   — a `12.3%` difference. At k=100, the difference drops to `0.99%`.

4. **k=60 is the literature default** (Cormack et al., 2009) but should be
   validated empirically on your specific corpus and query distribution. Use
   the experiment utility `run_k_experiment()` for this purpose.

---

## 5. Worked Example

**Input:**

```
Dense Ranking:
    A → rank 1
    B → rank 2
    C → rank 3

BM25 Ranking:
    C → rank 1
    A → rank 2
    D → rank 3
```

**RRF calculation (k = 60):**

```
RRF(A) = 1/(60+1) + 1/(60+2)   = 1/61 + 1/62   ≈ 0.016393 + 0.016129 = 0.032522
RRF(B) = 1/(60+2) + 0           = 1/62           ≈ 0.016129
RRF(C) = 1/(60+3) + 1/(60+1)   = 1/63 + 1/61   ≈ 0.015873 + 0.016393 = 0.032267
RRF(D) = 0         + 1/(60+3)   = 1/63           ≈ 0.015873
```

**Final Hybrid Ranking (descending by RRF score):**

| Rank | Chunk | RRF Score  | Dense Rank | BM25 Rank |
|------|-------|-----------|------------|-----------|
| 1    | A     | 0.032522  | 1          | 2         |
| 2    | C     | 0.032267  | 3          | 1         |
| 3    | B     | 0.016129  | 2          | absent    |
| 4    | D     | 0.015873  | absent     | 3         |

**Observations:**
- A appears at rank 1 because it was top-ranked in Dense *and* second in BM25.
- C jumps from rank 3 in Dense to rank 2 hybrid because it was rank 1 in BM25.
- B (absent from BM25) drops to rank 3 despite dense rank 2.
- D (absent from Dense) appears at rank 4 with only BM25's rank 3 contribution.

---

## 6. Duplicate Handling

Each chunk receives exactly one contribution per retrieval list. If `chunk-A`
appears at both rank 1 and rank 3 within the same Dense list (upstream bug),
only rank 1 is counted for that source.

A chunk appearing in both Dense and BM25 receives contributions from both:

```
RRF(chunk-A) = 1/(k + dense_rank) + 1/(k + bm25_rank)
```

---

## 7. Deterministic Tie-Breaking

When two chunks have identical RRF scores (rare but possible when they appear
at the same ranks in complementary lists), the secondary sort key is
`chunk_id` (alphabetical ascending).

This guarantees:
- The same query always produces the same hybrid ranking.
- The ordering is independent of Python's internal dictionary or set iteration order.

---

## 8. Multi-Source Fusion

The RRF implementation accepts an arbitrary number of ranked lists (M ≥ 1):

```python
reciprocal_rank_fusion(
    rankings={
        "dense": dense_results,
        "bm25":  bm25_results,
        "bm25_cross_encoder": additional_results,
        ...
    },
    k=60,
    top_k=10,
)
```

The score is simply the sum of contributions from all present sources:

```
RRF(d) = Σ_{i=1}^{M} [ 1 / (k + r_i(d)) ]   (if d appears in source i)
       + 0                                      (for sources where d is absent)
```

---

## 9. Architecture

```
                         Query
                           │
             ┌─────────────┴─────────────┐
             ▼                           ▼
      DenseRetriever                BM25Retriever
      (top dense_top_k candidates)  (top bm25_top_k candidates)
             │                           │
             ▼                           ▼
       Dense Ranking                BM25 Ranking
             │                           │
             └─────────────┬─────────────┘
                           ▼
                reciprocal_rank_fusion()
                  (k parameter, dedup)
                           │
                           ▼
                    Hybrid Ranking
                  (sorted by RRF score)
                           │
                           ▼
               HybridRetrievalResult[]
```

**Module locations:**

| Component | Path |
|---|---|
| RRF algorithm | `app/retrieval/rrf.py` |
| Hybrid retriever | `app/retrieval/hybrid_retriever.py` |
| k-experiment utility | `app/retrieval/rrf_experiment.py` |
| Models | `app/retrieval/models.py` |
| Exceptions | `app/retrieval/exceptions.py` |
| API endpoint | `app/api/retrieval.py` (`POST /api/retrieval/hybrid`) |

---

## 10. Failure Modes

### allow_degraded=False (default)

Any retrieval source failure raises `HybridRetrievalError` immediately.
The caller must handle it. This prevents silently serving incomplete results
without awareness.

### allow_degraded=True

If one source fails, the result is fused from surviving sources only.
Results are tagged with `metadata["degraded"] = True` and
`metadata["failed_sources"] = [...]`.

If all sources fail, `HybridRetrievalError` is raised regardless.

---

## 11. Using the k-Experiment Utility

```python
from app.retrieval.rrf_experiment import run_k_experiment, format_k_comparison_table

results = run_k_experiment(
    rankings={"dense": dense_results, "bm25": bm25_results},
    k_values=[20, 40, 60, 100],
)

print(format_k_comparison_table(results))
```

This produces a Markdown table comparing ranks and scores for all k values.
