# ADR-003: Hybrid Retrieval, Multi-Tenancy Isolation, and Failure Resilience

## Context
As DocAnalyser scales from prototype to a production RAG platform, document ingestion and retrieval required standardized failure handling, multi-tenancy enforcement, vector embedding lifecycle management, and deterministic ranking improvements.

Prior architecture had partial gaps:
1. Ingestion failures could leave documents stuck in indeterminate states without failure reasons or bounded retries.
2. Deleting documents in the primary PostgreSQL database risked leaving orphaned vector embeddings in Qdrant.
3. Multi-tenant document filtering was not uniformly enforced across dense vector queries and BM25 hybrid fusion.
4. Candidate reranking lacked a cross-encoder model with fallback and score sanitization.

## Decisions

### 1. Document Lifecycle and Bounded Retries
- Added the `QUEUED` status to the document state machine: `UPLOADED -> QUEUED -> PROCESSING -> INDEXED`.
- Documents transitioning to `FAILED` record a specific `failure_reason` and an incremented `retry_count`.
- Automatic and manual retries are strictly bounded to a maximum of 3 attempts (`MAX_INGESTION_RETRIES = 3`). Exceeding this bound permanently preserves the failure reason and prevents retry thrashing.

### 2. Cascade Vector Cleanup on Document Deletion
- Spring Boot `DocumentService.deleteDocument` invokes `RagServiceClient.deleteDocument` calling FastAPI `POST /api/v1/documents` with event `DOCUMENT_DELETED`.
- Deletes all chunk embeddings from the Qdrant collection associated with `document_id`, preventing zombie chunks from appearing in subsequent queries.

### 3. Multi-Tenancy and Owner Access Filtering
- Enforced `owner_id` filtering in `VectorStoreFilter`, `FilterBuilder`, and `RetrievalFilter`.
- Prevents cross-tenant document leakage by ensuring dense vector search payload filtering and BM25 retrieval only match chunks owned by or accessible to the requesting user/tenant.

### 4. Cross-Encoder Reranker with Fallback
- Introduced `CrossEncoderCandidateReranker` using `cross-encoder/ms-marco-MiniLM-L-6-v2`.
- Applied numerically stable sigmoid transformation to convert raw model logits to bounded `[0.0, 1.0]` scores.
- Implemented NaN and Infinite value sanitization.
- Implemented graceful degradation: if `sentence-transformers` is unavailable or inference fails, candidates fall back to candidate retrieval scores without aborting user requests.

### 5. Evaluation Benchmark and Metric Breakdown
- Established a 60-case benchmark dataset covering 7 critical RAG failure categories: `exact_fact`, `semantic`, `multi_chunk`, `multi_document`, `insufficient_evidence`, `misleading_assumption`, and `page_citation`.
- Added per-category aggregation in `EvaluationReport` to track hit rate @ k, recall @ k, MRR, answerability, and refusal rates by query type.

## Status
Accepted

## Consequences
- Guarantees data consistency across PostgreSQL and Qdrant.
- Prevents ingestion retry storms.
- Ensures multi-tenant isolation at the vector database level.
- Improves precision and grounding of context passed to LLM generation while maintaining sub-second fallback resilience.
