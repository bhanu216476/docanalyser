# Citation Verification

**Version:** Day 16 — V0.1  
**Module:** `app/verification/`  
**Branch:** `feature/citation-verification`

---

## Purpose

Citation mapping alone is insufficient. Mapping a citation `[1]` back to a document name and page number proves only that the LLM referenced a chunk — not that the chunk actually supports the claim it was cited for.

**Citation Verification** closes this gap by evaluating whether the factual content of each claim in the generated answer is actually supported by the evidence text of the referenced chunk.

Without citation verification:

```
Answer:  "Employees receive 20 casual leave days [1]."
[1] →    leave_policy.pdf, page 4
```

The citation *appears* valid — but the actual evidence says **12 days**, not **20**.

Citation verification detects this mismatch.

> **Critical distinction:** The verifier answers  
> *"Does the cited evidence support the claim?"*  
> It does NOT answer *"Is the claim true in the real world?"*  
> Verification is strictly against supplied RAG evidence.

---

## Verification Pipeline

```
Generated Answer
      │
      ▼
Extract Claims
(ClaimExtractor — sentence-level split, citation IDs associated)
      │
      ▼
For each Claim:
      │
      ├─ No citation IDs? ──────────────────────────► UNCITED
      │
      ├─ Citation ID missing from registry? ──────────► INVALID_CITATION
      │
      ▼
Resolve Evidence
(from authoritative Citation Registry — never re-retrieves from Qdrant)
      │
      ▼
Rule-Based Checks
(RuleBasedVerifier — deterministic, zero LLM calls)
      │
      ├─ Decisive result (mismatch/conflict)? ──────── return result
      │
      ▼
Semantic Verification (if mode = llm or hybrid)
(EvidenceVerifier — MockEvidenceVerifier or LLMEvidenceVerifier)
      │
      ▼
ClaimVerificationResult
      │
      ▼
VerificationResult (aggregated across all claims)
```

---

## Verification Statuses

| Status | Meaning |
|--------|---------|
| `SUPPORTED` | Evidence clearly supports the claim. Numbers, entities, and negation match. |
| `UNSUPPORTED` | Evidence contradicts or fails to support the claim. Includes numeric mismatch, entity mismatch, negation flip, or empty/irrelevant evidence. |
| `UNCERTAIN` | Evidence is ambiguous, incomplete, only partially addresses the claim, or conflicting evidence sources were cited. The verifier cannot make a confident determination. |
| `UNCITED` | The claim appears factual but has no `[N]` citation marker. The issue is a **missing evidence reference**, not a contradiction. Do not treat as UNSUPPORTED. |
| `INVALID_CITATION` | A citation ID referenced by the claim does not exist in the authoritative registry. Evidence cannot be resolved. |

### Aggregation Priority

When an answer contains multiple claims, the aggregate `overall_status` follows this priority (most severe wins):

```
UNSUPPORTED > UNCERTAIN > INVALID_CITATION > UNCITED > SUPPORTED
```

---

## Claim Extraction

The `ClaimExtractor` segments the generated answer into discrete factual statements using punctuation-based sentence splitting. Each sentence is associated with the citation IDs it references (extracted by the existing `CitationParser`).

- Citation markers (`[N]`) are **stripped** from the claim text before verification.
- Whitespace is normalized — trailing space before punctuation is removed.
- Sentences shorter than 5 non-whitespace characters are filtered.
- The extractor is deliberately simple (V0.1). A future semantic claim decomposition can replace it without changing the `CitationVerifier` interface.

---

## Evidence Resolution

For each citation ID in a claim:

```
[1]  →  Citation Registry (authoritative dict[int, Citation])
         │
         └── Citation.metadata["content"]  →  evidence text
```

- Evidence is resolved **exclusively** from the `CitationRegistry` produced by the `ContextBuilder`.  
- The verifier **never** re-retrieves chunks from Qdrant.  
- Evidence is **never fabricated** for missing or invalid citation IDs.  
- If `metadata["content"]` is empty, the claim is marked `UNSUPPORTED` (empty evidence).

---

## Rule-Based Verification

`RuleBasedVerifier` performs cheap, deterministic checks before any LLM call.

Rules applied in order (first decisive result wins):

| # | Check | Result |
|---|-------|--------|
| 1 | Citation ID absent from registry | `INVALID_CITATION` |
| 2 | Evidence text is empty | `UNSUPPORTED` |
| 3 | Claim text is empty | `UNSUPPORTED` |
| 4 | Numeric mismatch (≥10): claim has number N, evidence has different number M | `UNSUPPORTED` |
| 5 | Negation mismatch: claim positive + evidence negated (or vice versa) on shared key terms | `UNSUPPORTED` |
| 6 | Multi-evidence: different significant numbers across cited sources | `UNCERTAIN` |

**Important limitations:**
- Rule 4 only flags numbers ≥ 10 to avoid false positives from times (8 AM), page numbers, or version identifiers.
- Rule 5 uses negation word detection, not full semantic negation analysis. Ambiguous cases pass through to the semantic verifier.
- The rule layer is a **pre-filter only**. It does not confirm SUPPORTED — that requires semantic comparison.
- If no rule fires decisively, the claim escalates to semantic verification (in `llm` or `hybrid` mode), or is marked `UNCERTAIN` (in `rule_based` mode).

---

## Semantic Verification

When rules are inconclusive and `mode` is `llm` or `hybrid`, the claim is passed to an `EvidenceVerifier` implementation.

### EvidenceVerifier Protocol

```python
class EvidenceVerifier(Protocol):
    def verify(self, claim: str, evidence: str) -> SemanticVerificationOutcome: ...
    def verify_multi(self, claim: str, evidence_items: list[str]) -> SemanticVerificationOutcome: ...
```

### Implementations

| Class | Description |
|-------|-------------|
| `MockEvidenceVerifier` | Deterministic — uses substring heuristic or preset status. No API calls. Used in all tests. |
| `LLMEvidenceVerifier` | Calls a configured LLM provider with the versioned verification prompt. Parses structured JSON output. |

### LLM Output Contract

The `LLMEvidenceVerifier` requires structured JSON:

```json
{"status": "SUPPORTED", "reason": "Evidence explicitly states the same entitlement.", "confidence": 0.94}
```

- Invalid JSON → `UNCERTAIN` (never silently accepted)
- Unknown status string → `UNCERTAIN`
- `confidence` is optional; clamped to [0, 1] if present

---

## Verification Prompt

**Version:** `v1` (defined in `app/verification/verification_prompt.py`)

The prompt enforces:
1. System instruction appears **first** before any untrusted text
2. Explicit section delimiters: `[CLAIM START]`, `[CLAIM END]`, `[EVIDENCE START]`, `[EVIDENCE END]`
3. Instruction to use **only** supplied evidence — no outside knowledge
4. Structured JSON output requirement
5. Precise handling of numbers, entities, and negation

The prompt is designed to resist **prompt injection**: adversarial claim or evidence text cannot appear before the system instruction and therefore cannot override it.

---

## Failure Cases (All Tested)

| Case | Answer | Evidence | Expected |
|------|--------|----------|----------|
| 1 — Correct citation | "…12 casual leave days [1]." | "…12 casual leave days." | `SUPPORTED` |
| 2 — Wrong number | "…20 casual leave days [1]." | "…12 casual leave days." | `UNSUPPORTED` |
| 3 — Wrong entity | "…Finance portal [1]." | "…HR portal." | `UNSUPPORTED` (semantic) |
| 4 — Missing citation | "…12 casual leave days." | *(no registry)* | `UNCITED` |
| 5 — Invalid citation ID | "…12 casual leave days [99]." | *(only [1] in registry)* | `INVALID_CITATION` |
| 6 — Conflicting sources | "…12 days [1][2]." | [1]=12 days, [2]=15 days | `UNCERTAIN` |
| 7 — Partial support | "…12 days and 5 carry-over [1]." | "…12 casual leave days." | `UNCERTAIN` |
| 8 — Negation | "…eligible during probation [1]." | "…NOT eligible during probation." | `UNSUPPORTED` |
| 9 — Semantic paraphrase | "…twelve casual leave days [1]." | "…12 casual leave days." | `UNCERTAIN` (rules) / `SUPPORTED` (LLM) |
| 10 — Irrelevant evidence | "…12 casual leave days [1]." | "Cafeteria open 8 AM to 6 PM." | Not `SUPPORTED` |

---

## Multi-Citation Handling

When a claim cites multiple sources (e.g., `[1][2]`):

1. All cited IDs are resolved from the registry.
2. Rule-based conflict detection checks for contradicting numbers across sources.
3. If conflict detected → `UNCERTAIN`.
4. If all evidence collectively supports → `SUPPORTED` (semantic mode).
5. **One supporting citation is not sufficient if another contradicts.**

---

## Verification Policy

Controlled by `VerificationPolicy` and `app/core/config.py`:

```
CITATION_VERIFICATION_ENABLED=true
CITATION_VERIFICATION_MODE=rule_based   # rule_based | llm | hybrid
CITATION_VERIFICATION_FAIL_ON_UNSUPPORTED=false
```

For V0.1, `fail_on_unsupported=False` — unsupported claims are **flagged** in the verification result but do not raise exceptions or modify the answer.

---

## Unsupported Claim Policy

When verification finds `UNSUPPORTED`:

- The claim is **flagged** in the `VerificationResult`.
- The original answer is **not modified**.
- The calling pipeline receives the structured `VerificationResult` and can apply downstream handling.
- **No automatic answer correction is performed in V0.1.**

---

## Confidence Scores

If the semantic verifier returns a confidence score, it is preserved in `ClaimVerificationResult.confidence`.

> ⚠️ This score reflects the verifier's internal estimate and is **NOT a calibrated probability** unless the system has been formally calibrated. Do not use it as an objective truth indicator.

---

## Latency

The verifier records monotonic wall-clock latencies:

| Field | Description |
|-------|-------------|
| `rule_check_latency_ms` | Per-claim rule-based check time |
| `semantic_latency_ms` | Per-claim semantic verification time |
| `total_latency_ms` | Sum of rule + semantic per claim |
| `total_verification_latency_ms` | Full pass wall-clock time (on `VerificationResult`) |

Latency measurement does not influence the verification decision.

---

## Security

Both answer and evidence are treated as **untrusted text**:

- Answer text cannot redefine verification rules.
- Evidence text cannot inject verifier instructions.
- Document content cannot override system instructions.
- The verification prompt uses explicit `[CLAIM START]` / `[EVIDENCE START]` delimiters so system instructions always precede untrusted input.

This is a **defence-in-depth** measure. It reduces prompt injection risk but does not eliminate it for adversarial inputs.

---

## Limitations

1. **Not a truth oracle.** Citation verification evaluates only whether the supplied RAG evidence supports the claim. It does not check whether the evidence itself is factually correct.

2. **Rule-based numeric checks require numbers ≥ 10** to avoid false positives from times, version numbers, and single-digit quantities.

3. **Negation detection is heuristic.** Complex negation patterns (double negatives, implicit negation) may not be detected by the rule layer.

4. **Paraphrases require LLM verification.** The rule layer cannot detect that "twelve days" and "12 days" are equivalent. In `rule_based` mode these return `UNCERTAIN`.

5. **Evidence resolution depends on content storage.** The verifier reads `Citation.metadata["content"]`. If the ContextBuilder did not store chunk content in metadata, evidence is empty and claims are `UNSUPPORTED`. Future work: ensure chunk content is always stored in the registry.

6. **No automatic correction.** Flagged unsupported claims do not trigger answer regeneration in V0.1.
