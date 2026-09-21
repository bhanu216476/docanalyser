# RAG Confidence Scoring

## 1. Why Confidence Scoring Is Needed

In a Retrieval-Augmented Generation (RAG) pipeline, large language models (LLMs) can generate fluent, persuasive answers even when the retrieved evidence is weak, partial, or contradictory. Without confidence scoring, downstream applications and users treat all generated answers with equal trust.

The DocAnalyser Confidence Scoring mechanism answers a precise engineering question:

> **"How confident is the system that the generated answer is adequately supported by the retrieved evidence?"**

Crucially:
- Confidence is **NOT** a guarantee of real-world factual correctness.
- It evaluates the **adequacy and grounding** of the answer relative to retrieved context.
- It provides a diagnostic and explainable evaluation signal rather than an opaque black-box probability.

---

## 2. Confidence Formula

The overall confidence score is computed as a transparent, linear weighted combination of four normalized signals:

$$\text{Confidence} = w_{\text{retrieval}} \cdot S_{\text{retrieval}} + w_{\text{reranking}} \cdot S_{\text{reranking}} + w_{\text{citation}} \cdot S_{\text{citation}} + w_{\text{answer}} \cdot S_{\text{answer}}$$

Where:
- $S_{\text{retrieval}} \in [0.0, 1.0]$: Normalized candidate retrieval signal
- $S_{\text{reranking}} \in [0.0, 1.0]$: Normalized candidate reranker signal
- $S_{\text{citation}} \in [0.0, 1.0]$: Aggregate citation verification support signal
- $S_{\text{answer}} \in [0.0, 1.0]$: Deterministic answerability assessment signal
- $w_{\text{retrieval}}, w_{\text{reranking}}, w_{\text{citation}}, w_{\text{answer}} \ge 0$ with $\sum w_i = 1.0$
- The final score is strictly clamped to $[0.0, 1.0]$.

---

## 3. Signal Definitions

| Signal | Source Component | Meaning |
| :--- | :--- | :--- |
| **Retrieval Signal** ($S_{\text{retrieval}}$) | Dense / BM25 / RRF | Measures how strongly the query matched source chunks in early retrieval stages. |
| **Reranking Signal** ($S_{\text{reranking}}$) | BaseReranker / MockReranker | Measures deep cross-encoder or lexical/semantic relevance of top candidates after reranking. |
| **Citation Support Signal** ($S_{\text{citation}}$) | CitationVerifier / Rules / LLM | Measures whether claims made in the generated answer are grounded in the referenced evidence. |
| **Answerability Signal** ($S_{\text{answer}}$) | AnswerabilityEvaluator | Assesses whether the retrieved context and generated answer are sufficient to address the user's query without refusal. |

---

## 4. Score Normalization

Different retrieval systems output scores on incompatible scales:
- **Dense Cosine Similarity**: $[-1.0, 1.0]$ (typically $[0.0, 1.0]$). Clamped or linearly mapped to $[0.0, 1.0]$.
- **BM25 Lexical Scores**: $[0.0, +\infty)$. Soft-saturation mapping:
  $$S_{\text{BM25\_norm}} = \frac{s}{s + k_{\text{norm}}}$$
  where $k_{\text{norm}} = 10.0$ is the half-saturation constant ($s = 10 \to 0.5$).
- **Reciprocal Rank Fusion (RRF)**:
  $$s_{\text{RRF}} = \sum_{m \in \text{sources}} \frac{1}{k + r_m}$$
  For $M = 2$ retrieval sources (Dense + BM25) and $k = 60$, the theoretical maximum is $M / (k + 1) = 2 / 61 \approx 0.032787$. RRF scores are normalized relative to this theoretical maximum:
  $$S_{\text{RRF\_norm}} = \min\left(1.0, \frac{s_{\text{RRF}}}{M / (k + 1)}\right)$$
- **Reranker Scores**: Clamped to $[0.0, 1.0]$ for probability/mock scores, or transformed via standard logistic sigmoid $\sigma(s) = \frac{1}{1 + e^{-s}}$ for raw cross-encoder logits.
- **Empty Candidate Pool**: If no candidates are retrieved, all retrieval and reranking signals evaluate to $0.0$. Non-finite numbers (`NaN`, `Inf`) are safely clamped to $0.0$.

---

## 5. Initial Engineering Weights

| Component | Weight | Rationale |
| :--- | :--- | :--- |
| $w_{\text{retrieval}}$ | **0.20** | Rewards strong initial keyword and semantic search alignment. |
| $w_{\text{reranking}}$ | **0.25** | Reflects high-precision candidate reordering. |
| $w_{\text{citation}}$ | **0.35** | **Heaviest weight**: Grounded evidence support directly prevents ungrounded hallucinations. |
| $w_{\text{answer}}$ | **0.20** | Rewards full query answerability while penalizing explicit refusals or missing context. |
| **Total** | **1.00** | Strict sum-to-one constraint. |

> [!NOTE]
> These weights are initial engineering weights established through domain design, not scientifically validated or empirically learned probabilities.

---

## 6. Citation Verification Mapping

Using the Day 16 `CitationVerifier` and `VerificationStatus`, each claim's verification outcome is mapped to a deterministic support value:

| VerificationStatus | Support Value | Rationale |
| :--- | :--- | :--- |
| `SUPPORTED` | **1.0** | Cited evidence clearly verifies the factual claim. |
| `UNCERTAIN` | **0.5** | Evidence is ambiguous, conflicting, or incomplete. |
| `UNSUPPORTED` | **0.0** | Cited evidence contradicts or fails to support the claim. |
| `UNCITED` | **0.0** | Factual statement made without evidence citation. |
| `INVALID_CITATION` | **0.0** | Citation ID does not exist in the authoritative registry. |

For $N$ claims in the generated answer:

$$S_{\text{citation}} = \frac{1}{N} \sum_{i=1}^N \text{Support}(\text{claim}_i)$$

If $N = 0$ (e.g. empty answer or answer with no factual citations), $S_{\text{citation}} = 0.0$.

---

## 7. Answerability Mapping

The `AnswerabilityEvaluator` classifies the response state into deterministic categories:

| Status | Value | Trigger Conditions |
| :--- | :--- | :--- |
| `ANSWERABLE` | **1.0** | Evidence chunks exist, no refusal pattern detected, and all extracted claims are supported. |
| `PARTIALLY_ANSWERABLE` | **0.5** | Evidence exists, but claims are mixed (`SUPPORTED` and `UNSUPPORTED`/`UNCERTAIN`), or claims are uncertain. |
| `NOT_ANSWERABLE` | **0.0** | Empty query, empty answer, no evidence retrieved, explicit refusal ("I do not have enough information"), or all claims unsupported. |

---

## 8. Configuration

Configured via environment variables and application `Settings` (`app/core/config.py`):

```bash
# Weights (must sum to 1.0, each >= 0.0)
CONFIDENCE_RETRIEVAL_WEIGHT=0.20
CONFIDENCE_RERANKING_WEIGHT=0.25
CONFIDENCE_CITATION_WEIGHT=0.35
CONFIDENCE_ANSWERABILITY_WEIGHT=0.20

# Diagnostic Bands Thresholds
CONFIDENCE_HIGH_THRESHOLD=0.80
CONFIDENCE_LOW_THRESHOLD=0.50
```

Validation rules:
- All weights must be non-negative ($\ge 0.0$).
- Sum of weights must equal $1.0$ within numerical tolerance ($10^{-5}$).
- Configuration fails fast with a `ValueError` if constraints are violated.

---

## 9. Example Calculations

### Worked Example 1 (Standard High Confidence)
*Note: This is an illustrative engineering example, not an empirical statistical validation.*

Given:
- Retrieval Signal ($S_{\text{retrieval}}$) = $0.90$
- Reranking Signal ($S_{\text{reranking}}$) = $0.80$
- Citation Support ($S_{\text{citation}}$) = $1.00$
- Answerability ($S_{\text{answer}}$) = $0.90$

Calculation:
$$\text{Confidence} = 0.20(0.90) + 0.25(0.80) + 0.35(1.00) + 0.20(0.90)$$
$$\text{Confidence} = 0.18 + 0.20 + 0.35 + 0.18 = 0.9100$$
- Result: **0.9100**
- Diagnostic Band: **HIGH** ($\ge 0.80$)

### Worked Example 2 (Strong Retrieval, Weak Citation)
Given:
- $S_{\text{retrieval}} = 1.00$
- $S_{\text{reranking}} = 1.00$
- $S_{\text{citation}} = 0.00$ (all claims unsupported)
- $S_{\text{answer}} = 0.50$ (partial)

Calculation:
$$\text{Confidence} = 0.20(1.00) + 0.25(1.00) + 0.35(0.00) + 0.20(0.50) = 0.20 + 0.25 + 0.00 + 0.10 = 0.5500$$
- Result: **0.5500**
- Diagnostic Band: **MEDIUM** (shows that strong retrieval cannot hide unsupported claims).

### Worked Example 3 (Multiple Claims Support)
An answer contains 4 claims:
1. Claim 1: `SUPPORTED` (1.0)
2. Claim 2: `SUPPORTED` (1.0)
3. Claim 3: `UNCERTAIN` (0.5)
4. Claim 4: `UNSUPPORTED` (0.0)

$$S_{\text{citation}} = \frac{1.0 + 1.0 + 0.5 + 0.0}{4} = \frac{2.5}{4} = 0.6250$$

---

## 10. Edge Cases Handled

1. **No retrieved documents**: Retrieval and reranking signals evaluate to $0.0$; answerability evaluates to $0.0$; confidence is $0.0$ (`LOW`).
2. **Empty answer**: Evaluates to $0.0$ confidence.
3. **Missing citation verification**: Defaults citation support to $0.0$ rather than assuming perfection.
4. **Uncited factual answers**: Claims without citation markers receive `UNCITED` ($0.0$), penalizing the citation support score.
5. **Non-finite numbers**: Any `NaN` or `Inf` score is safely sanitized to $0.0$.
6. **Conflicting evidence**: Receives `UNCERTAIN` ($0.5$), making epistemic ambiguity visible.

---

## 11. Limitations

1. **Not a Proof of Truth**: The score measures consistency with retrieved text, not real-world ground truth. If the retrieved document itself contains misinformation, the RAG answer may be rated high-confidence if faithfully cited.
2. **Fixed Engineering Weights**: Default weights are chosen via heuristic design and may not be optimal for every specialized domain.
3. **Extraction Dependency**: Citation support depends on the claim extraction heuristics and citation marker syntax.

---

## 12. Why the Score Is NOT a Calibrated Probability

- A score of $0.90$ does **NOT** mean there is a $90\%$ probability that the answer is factually true.
- Confidence scoring is a deterministic multi-signal engineering metric.
- It lacks empirical calibration against an annotated ground-truth test set (such as Platt scaling or isotonic regression).
- It should only be used as a relative ranking, diagnostic signal, or threshold trigger (e.g. flagging answers for human review).

---

## 13. Future Calibration Requirements

To transition confidence scoring from an engineering index to a true calibrated probability:
1. **Labeled Calibration Dataset**: Collect $(query, context, answer, is\_correct)$ tuples with human ground truth labels.
2. **Calibration Curves**: Measure Expected Calibration Error (ECE) and plot reliability diagrams.
3. **Statistical Scaling**: Train a logistic or Platt regression model over the feature vector $(S_{\text{retrieval}}, S_{\text{reranking}}, S_{\text{citation}}, S_{\text{answer}})$.
4. **Selective Prediction**: Benchmark accuracy vs. coverage curves to select actionable cutoff thresholds for fallback behaviors.
