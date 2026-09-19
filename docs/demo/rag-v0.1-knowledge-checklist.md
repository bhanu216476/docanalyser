# DocAnalyser RAG V0.1 — Developer Knowledge Checklist

This document provides definitive, engineering-grounded explanations for every fundamental concept in the DocAnalyser RAG V0.1 pipeline. Each answer reflects the actual Python implementations across `app/ingestion/`, `app/embeddings/`, `app/vector_store/`, `app/retrieval/`, `app/reranking/`, `app/context/`, `app/llm/`, and `app/pipeline/`.

---

## 1. Ingestion & Preprocessing

### What is chunking?
**Chunking** is the deterministic process of partitioning a continuous document's raw text content into smaller, self-contained text segments ("chunks"). In DocAnalyser, chunking is performed by `BaseChunker` subclasses (specifically `RecursiveChunker` and `FixedSizeChunker`). Each produced chunk is encapsulated by the immutable `Chunk` model containing:
- `chunk_id`: A deterministic hash combining the parent document ID and chunk index (e.g. `doc_id:0`).
- `document_id`: The SHA-256 hash or canonical identifier of the source document.
- `chunk_index`: 0-based sequential position within the parent document.
- `content`: Non-empty normalized text slice.
- `metadata`: Source provenance (`file_name`, `page_number`, `section`, `headings`).

### Why do we chunk documents?
1. **Model Context & Token Limits**: Embedding models (`text-embedding-3-small`, max 8,191 tokens) and LLM context windows cannot ingest entire multi-hundred page documents in a single vector or prompt.
2. **Retrieval Precision**: A vector representing an entire 50-page PDF averages out topic nuances. Embedding a 500-character paragraph produces a sharp semantic representation targeted to specific facts.
3. **Evidence Localization & Citations**: Chunking allows pinpoint attribution (`[1] leave_policy.pdf, page 4`) rather than citing a 100-page book as a generic source.
4. **Token Budgeting**: The LLM prompt context can selectively assemble only the top 3–5 relevant chunks (e.g., within a 1,500 token limit), minimizing prompt cost and latency while avoiding distractors.

---

## 2. Vector Representations & Dense Storage

### What is an embedding?
An **embedding** is a dense, continuous numerical vector $\vec{v} \in \mathbb{R}^D$ (in our project, $D = 1536$ for OpenAI `text-embedding-3-small` or configured dimension) where geometric distance (e.g., Cosine angle) corresponds to semantic meaning. In `EmbeddingService`, strings are converted into floating-point vectors such that texts with similar conceptual meaning lie close together in high-dimensional vector space.

### Why do we need embeddings?
Embeddings enable **semantic search**. Lexical search (exact keyword matching) fails when users ask questions using synonyms, paraphrases, or conceptual queries (e.g., searching for "quota for informal time off" to retrieve "Employees receive 12 casual leave days"). Embeddings bridge the vocabulary mismatch problem by capturing the latent meaning of queries and documents.

### What is dense retrieval?
**Dense retrieval** is the process of retrieving candidate document chunks by comparing the embedded query vector $\vec{q}$ against a pre-indexed database of chunk vectors $\{\vec{d}_i\}$ using similarity metrics (cosine similarity, dot product, or Euclidean distance). In `DenseRetriever`:
1. The user query is passed to `EmbeddingService.embed_texts([query])`.
2. The vector is submitted to Qdrant via `client.query_points()`.
3. The top-$K$ nearest chunks are returned ranked by similarity score.

### What does Qdrant do?
**Qdrant** is a high-performance vector database that stores chunk embeddings alongside structured metadata payloads. In DocAnalyser:
- It maintains HNSW graphs for approximate nearest-neighbor (ANN) search.
- It provides deterministic point ID deduplication (using UUIDv5 over `chunk_id`).
- It enforces payload schemas (`document_id`, `file_type`, `source`).
- It executes server-side metadata filtering (`FilterBuilder` / `VectorStoreFilter`) before ANN scoring, ensuring hard constraints (e.g., filter by department or document ID) are enforced natively without post-filtering overhead.

---

## 3. Lexical Retrieval & BM25

### What is BM25?
**BM25 (Best Matching 25)** is a probabilistic ranking function used for lexical (sparse) information retrieval. It estimates the relevance of a document chunk $D$ to a search query $Q$ based on term frequencies, inverse document frequencies, and document length normalization.

### What are TF and IDF?
- **Term Frequency (TF)**: The number of times a query term $t$ appears in document chunk $D$, denoted $\text{TF}(t, D)$. In BM25, TF exhibits non-linear saturation: repeated occurrences of a word provide diminishing marginal relevance:
  $$\frac{\text{TF}(t, D) \cdot (k_1 + 1)}{\text{TF}(t, D) + k_1 \cdot \left(1 - b + b \cdot \frac{|D|}{\text{avgdl}}\right)}$$
- **Inverse Document Frequency (IDF)**: A measure of how much information a term provides across the entire corpus. Terms that occur in almost every document (e.g., "the", "policy") receive near-zero IDF, whereas rare, distinctive keywords (e.g., "probation", "casual") receive high IDF. In `BM25Index`:
  $$\text{IDF}(t) = \ln\left(1 + \frac{N - \text{df}(t) + 0.5}{\text{df}(t) + 0.5}\right)$$
  (guaranteed non-negative by adding 1.0).

### Why does document length matter in BM25?
Long documents naturally contain more words and therefore higher raw term frequencies simply due to length, not necessarily greater topical relevance. The BM25 parameter $b \in [0, 1]$ (default $0.75$ in `settings.bm25_b`) normalizes term frequencies by the ratio of document length $|D|$ to average document length $\text{avgdl}$:
- If $|D| > \text{avgdl}$, the denominator increases, penalizing verbosity.
- If $|D| < \text{avgdl}$, the document is boosted because matching a term in a short, concise chunk is stronger evidence of relevance.

---

## 4. Hybrid Retrieval & Rank Fusion

### Why can't Dense and BM25 scores simply be added?
Dense cosine similarity scores and BM25 scores live on **incompatible mathematical scales with entirely different score distributions**:
- Cosine similarity produces scores bounded in $[-1.0, 1.0]$ (often clustered tightly between $0.6$ and $0.85$).
- BM25 produces unbounded non-negative scores $[0, \infty)$ dependent on query length and IDF weights (often between $2.0$ and $25.0$).
Linearly summing them without calibration would cause BM25 to completely dominate dense similarity, or vice-versa, making the search behavior unstable across different queries.

### What does RRF solve?
**Reciprocal Rank Fusion (RRF)** solves score incomparability by discarding raw score values entirely and fusing candidate documents based strictly on their **ordinal rank positions**:
$$\text{RRF}(d) = \sum_{m \in \text{systems}} \frac{1}{k + r_m(d)}$$
where $r_m(d)$ is the 1-based rank of document $d$ in retrieval system $m$. RRF guarantees that documents performing consistently well across both dense and sparse retrieval receive the highest fused priority, with zero vulnerability to score scale mismatches.

### What does $k$ mean in RRF?
The parameter $k$ (default $60$ in `settings.rrf_k`) is a ranking smoothing constant that controls how rapidly a document's score decays as its rank position drops:
- For rank $1$, score is $\frac{1}{60 + 1} \approx 0.01639$.
- For rank $2$, score is $\frac{1}{60 + 2} \approx 0.01613$.
A higher $k$ (e.g., $60$) ensures that high-ranking results from one system do not overwhelmingly eclipse relevant results appearing slightly lower down in the other system, promoting balanced consensus between dense and lexical signals.

---

## 5. Reranking

### What does a reranker do?
A **reranker** is a high-precision, computationally intensive second-stage ranking model (such as a Cross-Encoder or neural scoring module, abstracted by `BaseReranker` / `MockReranker`). Unlike dual-encoder dense retrieval (which encodes query and document independently into vectors), a reranker processes the query and document chunk **together** through full cross-attention layers, computing a direct relevance score $s(q, d)$.

### Why do we rerank after retrieval?
1. **Efficiency vs. Accuracy Tradeoff**: Running a heavy cross-encoder over 100,000 document chunks in a database is computationally prohibitive ($O(N)$ transformer passes).
2. **Two-Stage Architecture**:
   - *Stage 1 (First-Stage Retrieval)*: Dense + BM25 quickly filters the collection of 100,000 chunks down to a high-recall candidate pool (e.g., top 20 candidates in $<10\text{ms}$).
   - *Stage 2 (Reranking)*: The reranker scores only those 20 candidates with deep token-level cross-attention, reordering them to put the most precise evidence at rank 1.

---

## 6. Context Engineering & Citations

### What is the Context Builder?
The `ContextBuilder` (`app/context/context_builder.py`) transforms ranked retrieval candidates into a clean, token-bounded, deduplicated, and citation-ready context block for LLM prompt injection. It acts as the strict firewall between raw retrieval output and the LLM.

### Why do we need a token budget?
LLMs have finite context windows, and every prompt token increases monetary cost, time-to-first-token (TTFT) latency, and the risk of "Lost in the Middle" attention degradation. The `BudgetTracker` in `ContextBuilder` enforces a strict token budget (e.g., 2,000 tokens via `TiktokenCounter`), selecting candidates in rank order and dropping or truncating lower-ranked chunks that exceed the budget.

### How are citation IDs created?
Citation IDs are assigned sequentially (`[1]`, `[2]`, `[3]`, ...) by `format_citation_id` as chunks are admitted into the token budget in rank order. For each admitted chunk, `extract_citation` captures an immutable `Citation` record:
- `citation_id`: e.g. `"[1]"`
- `chunk_id`: source chunk hash
- `document_id`: parent document ID
- `file_name`: e.g. `"company_leave_policy.pdf"`
- `page_number`: physical page from which the text was extracted
- `section`: Markdown or structural header (if applicable)

---

## 7. Grounding, Generation & Refusal

### What makes an answer grounded?
An answer is **grounded** if and only if:
1. Every factual claim is directly verifiable from the evidence provided in the prompt context.
2. The answer explicitly references verified citation markers (`[1]`) corresponding to the evidence chunks.
3. The LLM does not extrapolate, assume, or utilize prior pre-training parametric knowledge that contradicts or exceeds the provided context.

### What should happen when evidence is missing?
When the retrieved evidence does not contain information to answer the question (e.g. asking about "international travel allowance" in a sick leave policy):
1. The LLM must explicitly state that the supplied documents do not contain sufficient information (a **grounded refusal**).
2. The pipeline must **not** fabricate citations. In `_verify_and_attribute_citations()`, detection of insufficient-information phrasing automatically empties the returned citations list (`[]`).

### What does the LLM actually receive?
The LLM does **not** receive a raw vector, a Qdrant collection, or an unformatted text blob. It receives a structured `Prompt` containing:
1. **System Prompt**: Grounding constraints, instruction to answer solely based on supplied context, citation formatting rules (`[1]`), and strict refusal instructions.
2. **Context Block**: Clean evidence chunks prefixed with their citation identifiers:
   ```text
   [1]
   source: company_leave_policy.pdf
   page: 1

   Employees receive 12 casual leave days per calendar year.
   ```
3. **User Query**: The clean, unadulterated question string.
