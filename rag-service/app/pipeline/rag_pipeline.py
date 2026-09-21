"""
RAG Pipeline Orchestrator for DocAnalyser RAG V0.1.

Coordinates the complete end-to-end RAG workflow:
    Document Ingestion:
        File (PDF / TXT / MD) → BaseLoader → Document
        → BaseChunker → Chunk[]
        → EmbeddingService → EmbeddedChunk[]
        → QdrantVectorStore (Dense) + BM25Index (Lexical)

    Query Processing:
        User Query (+ optional RetrievalFilter)
        → DenseRetriever + BM25Retriever (Retrieval)
        → Reciprocal Rank Fusion (RRF)
        → Candidate Reranker (BaseReranker)
        → ContextBuilder (Token budgeting, deduplication, citation mapping)
        → PromptBuilder (Versioned prompt assembly)
        → LLMProvider (Generation)
        → RAGResponse (Grounded answer, verified citations, latency breakdown)
"""

from __future__ import annotations

from collections.abc import Sequence
import inspect
import logging
from pathlib import Path
import re
import time
from typing import Any, Optional, Union

from qdrant_client import QdrantClient

from app.citations.mapper import CitationMapper
from app.confidence.calculator import ConfidenceCalculator
from app.confidence.signals import SignalExtractor
from app.context.context_builder import ContextBuilder
from app.context.models import BuiltContext, Citation, ContextBuilderConfig
from app.core.config import settings
from app.embeddings.providers import FakeEmbeddingProvider
from app.embeddings.service import EmbeddingService
from app.ingestion.base import BaseLoader
from app.ingestion.chunking import BaseChunker, Chunk, RecursiveChunker
from app.ingestion.markdown_loader import MarkdownLoader
from app.ingestion.pdf_loader import PDFLoader
from app.ingestion.txt_loader import TxtLoader
from app.llm.prompt_builder import PromptBuilder
from app.llm.prompts.models import Prompt, PromptVersion
from app.llm.providers import FakeLLMProvider, LLMProvider, LLMResponse
from app.pipeline.models import IngestionResponse, RAGQueryRequest, RAGResponse
from app.reranking.base import BaseReranker
from app.reranking.mock_reranker import MockReranker
from app.reranking.models import RerankedResult
from app.retrieval.bm25_index import BM25Index
from app.retrieval.bm25_retriever import BM25Retriever
from app.retrieval.dense_retriever import DenseRetriever
from app.retrieval.hybrid_retriever import HybridRetriever
from app.retrieval.models import (
    HybridRetrievalResult,
    RetrievalFilter,
    RetrievalResult,
)
from app.retrieval.rrf import reciprocal_rank_fusion
from app.vector_store.qdrant_client import create_qdrant_client
from app.vector_store.qdrant_store import QdrantVectorStore
from app.verification.citation_verifier import CitationVerifier
from app.verification.models import VerificationPolicy, VerificationResult

logger = logging.getLogger(__name__)


class RAGPipelineError(Exception):
    """Base exception for RAG pipeline errors."""


class IngestionError(RAGPipelineError):
    """Raised when document ingestion fails."""


class QueryPipelineError(RAGPipelineError):
    """Raised when query retrieval or generation fails."""


class RAGPipeline:
    """
    Production-ready orchestrator for the DocAnalyser RAG V0.1 pipeline.

    Supports dependency injection for all subsystem components with sensible
    defaults for local development, automated testing, and production deployment.
    """

    def __init__(
        self,
        vector_store: Optional[QdrantVectorStore] = None,
        bm25_index: Optional[BM25Index] = None,
        embedding_service: Optional[EmbeddingService] = None,
        chunker: Optional[BaseChunker] = None,
        hybrid_retriever: Optional[HybridRetriever] = None,
        reranker: Optional[BaseReranker] = None,
        context_builder: Optional[ContextBuilder] = None,
        prompt_builder: Optional[PromptBuilder] = None,
        llm_provider: Optional[LLMProvider] = None,
        citation_mapper: Optional[CitationMapper] = None,
        citation_verifier: Optional[CitationVerifier] = None,
        confidence_calculator: Optional[ConfidenceCalculator] = None,
        in_memory: bool = False,
    ) -> None:
        """
        Initialize the RAG pipeline with components or auto-configured defaults.

        Args:
            vector_store: Qdrant vector store instance for dense embeddings.
            bm25_index: BM25 inverted index for lexical search.
            embedding_service: Embedding generation service.
            chunker: Document chunker (defaults to RecursiveChunker).
            hybrid_retriever: Hybrid retriever combining dense and BM25 search.
            reranker: Candidate reranker (defaults to MockReranker).
            context_builder: Context assembler with token budgeting.
            prompt_builder: Versioned prompt builder.
            llm_provider: LLM text generator (defaults to FakeLLMProvider).
            in_memory: If True, forces in-memory Qdrant client for local testing.
        """
        # 1. Embedding service & dimension
        self.embedding_service = embedding_service or EmbeddingService(
            provider=FakeEmbeddingProvider(dimension=settings.qdrant_vector_size)
        )
        vector_size = getattr(
            self.embedding_service, "vector_size", settings.qdrant_vector_size
        )

        # 2. Vector store
        if vector_store is not None:
            self.vector_store = vector_store
        else:
            if in_memory:
                client = create_qdrant_client(location=":memory:")
            else:
                try:
                    client = create_qdrant_client()
                    # Test connectivity
                    client.get_collections()
                except Exception as exc:
                    logger.warning(
                        "Remote Qdrant connection failed (%s); falling back to in-memory store.",
                        exc,
                    )
                    client = create_qdrant_client(location=":memory:")

            self.vector_store = QdrantVectorStore(
                client=client,
                collection_name=settings.qdrant_collection_name,
                vector_size=vector_size,
                distance=settings.qdrant_distance,
            )
            self.vector_store.ensure_collection()

        # 3. BM25 Index
        self.bm25_index = bm25_index if bm25_index is not None else BM25Index()

        # 4. Chunker
        self.chunker = chunker or RecursiveChunker(
            chunk_size=500,
            overlap=50,
        )

        # 5. Hybrid Retriever
        if hybrid_retriever is not None:
            self.hybrid_retriever = hybrid_retriever
            self.dense_retriever = getattr(hybrid_retriever, "dense_retriever", None)
            self.bm25_retriever = getattr(hybrid_retriever, "bm25_retriever", None)
        else:
            self.dense_retriever = DenseRetriever(
                embedding_service=self.embedding_service,
                qdrant_client=self.vector_store._client,
                collection_name=self.vector_store.collection_name,
                vector_size=vector_size,
                max_top_k=settings.retrieval_max_top_k,
            )
            self.bm25_retriever = BM25Retriever(
                index=self.bm25_index,
                k1=settings.bm25_k1,
                b=settings.bm25_b,
                max_top_k=settings.bm25_max_top_k,
            )
            self.hybrid_retriever = HybridRetriever(
                dense_retriever=self.dense_retriever,
                bm25_retriever=self.bm25_retriever,
                k=settings.rrf_k,
                dense_top_k=settings.hybrid_dense_top_k,
                bm25_top_k=settings.hybrid_bm25_top_k,
                max_top_k=settings.hybrid_max_top_k,
                candidate_top_k=settings.hybrid_candidate_top_k,
            )

        # 6. Reranker
        self.reranker = reranker or MockReranker(
            default_top_k=settings.reranker_default_top_k
        )

        # 7. Context Builder
        self.context_builder = context_builder or ContextBuilder()

        # 8. Prompt Builder
        self.prompt_builder = prompt_builder or PromptBuilder()

        # 9. LLM Provider
        self.llm_provider = llm_provider or FakeLLMProvider()

        # 10. Citation Mapper
        self.citation_mapper = citation_mapper or CitationMapper()

        # 11. Citation Verifier
        if citation_verifier is not None:
            self.citation_verifier = citation_verifier
        else:
            mode = getattr(settings, "citation_verification_mode", "rule_based")
            enabled = getattr(settings, "citation_verification_enabled", True)
            policy = VerificationPolicy(enabled=enabled, mode=mode)
            self.citation_verifier = CitationVerifier(policy=policy)

        # 12. Confidence Calculator
        self.confidence_calculator = confidence_calculator or ConfidenceCalculator()

        logger.info(
            "RAGPipeline initialized successfully (collection=%s, vector_size=%d, in_memory=%s)",
            self.vector_store.collection_name,
            vector_size,
            in_memory,
        )

    # -----------------------------------------------------------------------
    # Document Ingestion
    # -----------------------------------------------------------------------

    def ingest(
        self,
        file_path: Union[str, Path],
        batch_size: Optional[int] = None,
    ) -> IngestionResponse:
        """
        Ingest a document into the RAG system.

        Stages:
            1. Document Loading (PDF, TXT, or MD)
            2. Structure-aware Chunking
            3. Embedding Generation
            4. Vector Store Upsert (Qdrant)
            5. Inverted Index Registration (BM25)

        Args:
            file_path: Absolute or relative path to the file.
            batch_size: Batch size for embedding and vector upserts.

        Returns:
            IngestionResponse containing document metadata, chunk count,
            and high-resolution stage latency breakdown.

        Raises:
            IngestionError: If file loading, chunking, or indexing fails.
        """
        path = Path(file_path)
        if not path.is_file():
            raise IngestionError(f"Target file does not exist or is not a file: {file_path}")

        latencies: dict[str, float] = {}
        t_total_start = time.perf_counter()

        # 1. Select appropriate loader
        ext = path.suffix.lower().lstrip(".")
        loader: BaseLoader
        if ext == "pdf":
            loader = PDFLoader()
        elif ext in ("txt", "text"):
            loader = TxtLoader()
        elif ext in ("md", "markdown"):
            loader = MarkdownLoader()
        else:
            raise IngestionError(
                f"Unsupported document extension '.{ext}'. "
                f"Supported extensions are: pdf, txt, md"
            )

        # Stage 1: Load Document
        t0 = time.perf_counter()
        try:
            document = loader.load(path)
        except Exception as exc:
            logger.error("Document loading failed for '%s': %s", file_path, exc)
            raise IngestionError(f"Document loading failed: {exc}") from exc
        latencies["load_ms"] = (time.perf_counter() - t0) * 1000.0

        # Stage 2: Chunk Document
        t1 = time.perf_counter()
        try:
            chunks = self.chunker.chunk(document)
        except Exception as exc:
            logger.error("Document chunking failed for '%s': %s", file_path, exc)
            raise IngestionError(f"Document chunking failed: {exc}") from exc
        latencies["chunk_ms"] = (time.perf_counter() - t1) * 1000.0

        # Resolve canonical document ID
        doc_id = document.metadata.get("document_id") if isinstance(document.metadata, dict) else None
        if not doc_id and chunks:
            doc_id = getattr(chunks[0], "document_id", None)
        if not doc_id:
            try:
                doc_id = document.to_canonical_metadata().document_id
            except Exception:
                doc_id = path.stem

        if not chunks:
            logger.warning("Ingestion produced 0 chunks for document '%s'", doc_id)
            latencies["total_ms"] = (time.perf_counter() - t_total_start) * 1000.0
            return IngestionResponse(
                document_id=doc_id,
                file_name=path.name,
                file_type=ext,
                chunk_count=0,
                latency_breakdown_ms=latencies,
            )

        # Stage 3: Embedding Generation
        t2 = time.perf_counter()
        try:
            embedded_chunks = self.embedding_service.embed_chunks(chunks)
        except Exception as exc:
            logger.error("Embedding generation failed: %s", exc)
            raise IngestionError(f"Embedding generation failed: {exc}") from exc
        latencies["embed_ms"] = (time.perf_counter() - t2) * 1000.0

        # Stage 4: Vector Store Upsert
        t3 = time.perf_counter()
        try:
            upsert_batch_size = batch_size or settings.qdrant_batch_size
            self.vector_store.upsert_chunks(
                chunks=chunks,
                embeddings=[ec.embedding for ec in embedded_chunks],
                batch_size=upsert_batch_size,
            )
        except Exception as exc:
            logger.error("Vector store upsert failed: %s", exc)
            raise IngestionError(f"Vector store upsert failed: {exc}") from exc
        latencies["vector_store_ms"] = (time.perf_counter() - t3) * 1000.0

        # Stage 5: BM25 Inverted Index
        t4 = time.perf_counter()
        try:
            self.bm25_index.index_chunks(chunks)
        except Exception as exc:
            logger.error("BM25 indexing failed: %s", exc)
            raise IngestionError(f"BM25 indexing failed: {exc}") from exc
        latencies["bm25_ms"] = (time.perf_counter() - t4) * 1000.0

        latencies["total_ms"] = (time.perf_counter() - t_total_start) * 1000.0

        logger.info(
            "Document '%s' successfully ingested: %d chunks indexed in %.2fms",
            path.name,
            len(chunks),
            latencies["total_ms"],
        )

        return IngestionResponse(
            document_id=doc_id,
            file_name=path.name,
            file_type=ext,
            chunk_count=len(chunks),
            latency_breakdown_ms=latencies,
        )

    # -----------------------------------------------------------------------
    # Step-by-Step Retrieval & Processing Pipeline
    # -----------------------------------------------------------------------

    def retrieve(
        self,
        query: str,
        filters: Optional[RetrievalFilter] = None,
        top_k: Optional[int] = None,
    ) -> tuple[list[RetrievalResult], list[RetrievalResult]]:
        """
        Execute dense and BM25 retrievers independently.

        Returns:
            Tuple of (dense_results, bm25_results).
        """
        k = top_k or settings.retrieval_default_top_k
        dense_results = self.dense_retriever.retrieve(query=query, top_k=k, filters=filters)
        bm25_results = self.bm25_retriever.retrieve(query=query, top_k=k, filters=filters)
        return dense_results, bm25_results

    def fuse(
        self,
        dense_results: list[RetrievalResult],
        bm25_results: list[RetrievalResult],
        top_k: Optional[int] = None,
    ) -> list[HybridRetrievalResult]:
        """
        Fuse dense and BM25 candidate lists using Reciprocal Rank Fusion (RRF).
        """
        k = top_k or settings.hybrid_default_top_k
        return reciprocal_rank_fusion(
            rankings={"dense": dense_results, "bm25": bm25_results},
            k=settings.rrf_k,
            top_k=k,
        )

    def rerank(
        self,
        query: str,
        candidates: Sequence[RetrievalResult],
        top_k: Optional[int] = None,
    ) -> list[RerankedResult]:
        """
        Rerank candidate results using the configured candidate reranker.
        """
        k = top_k or settings.reranker_default_top_k
        return self.reranker.rerank(query=query, documents=candidates, top_k=k)

    def build_context(
        self,
        reranked_results: Sequence[Union[RetrievalResult, RerankedResult]],
        token_budget: Optional[int] = None,
        max_chunks: Optional[int] = None,
    ) -> BuiltContext:
        """
        Build an LLM-ready deduplicated context within the token budget.
        """
        budget = token_budget if token_budget is not None else settings.context_token_budget
        chunks_cap = max_chunks if max_chunks is not None else settings.context_max_chunks
        config = ContextBuilderConfig(
            token_budget=budget,
            max_chunks=chunks_cap,
            include_metadata=settings.context_include_metadata,
            include_scores=settings.context_include_scores,
            oversized_chunk_policy=settings.context_oversized_policy,
        )
        return self.context_builder.build(reranked_results, config=config)

    def build_prompt(
        self,
        query: str,
        built_context: BuiltContext,
        version: Optional[str] = None,
    ) -> Prompt:
        """
        Assemble a versioned Prompt from the user query and built context.
        """
        prompt_ver = version or settings.prompt_version
        return self.prompt_builder.build(
            query=query,
            context=built_context,
            version=prompt_ver,
        )

    def generate(self, prompt: Prompt) -> LLMResponse:
        """
        Generate grounded answer text via the LLM provider.
        """
        prompt_text = (
            f"{prompt.system_prompt}\n\n"
            f"Evidence Context:\n{prompt.context_text}\n\n"
            f"User Question:\n{prompt.query}"
        )
        generate = self.llm_provider.generate
        if "model" not in inspect.signature(generate).parameters:
            return generate(prompt)  # type: ignore[call-arg]

        return generate(
            prompt_text,
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            max_output_tokens=settings.llm_max_output_tokens,
        )

    # -----------------------------------------------------------------------
    # End-to-End Query Orchestration
    # -----------------------------------------------------------------------

    def query(
        self,
        request: Union[RAGQueryRequest, str],
        top_k: Optional[int] = None,
        prompt_version: Optional[str] = None,
        filters: Optional[RetrievalFilter] = None,
    ) -> RAGResponse:
        """
        Execute the complete RAG query pipeline end-to-end.

        Workflow:
            Query → Dense + BM25 Retrieval → RRF Fusion → Reranking
            → Context Building & Citation Mapping → Prompt Assembly
            → LLM Generation → Citation Verification & RAGResponse

        Args:
            request: RAGQueryRequest model or raw query string.
            top_k: Optional top_k override.
            prompt_version: Optional prompt version override ('v1', 'v2', 'v3').
            filters: Optional metadata filters.

        Returns:
            RAGResponse containing grounded answer, verified citations,
            and latency breakdown.
        """
        if isinstance(request, str):
            query_str = request.strip()
            req_top_k = top_k
            req_version = prompt_version or settings.prompt_version
            req_filters = filters
        else:
            query_str = request.query.strip()
            req_top_k = request.top_k or top_k
            req_version = request.prompt_version or prompt_version or settings.prompt_version
            req_filters = request.filters or filters

        if not query_str:
            raise QueryPipelineError("Query text cannot be empty or whitespace-only.")

        latencies: dict[str, float] = {}
        metadata: dict[str, Any] = {}
        t_total_start = time.perf_counter()

        # Step 1: Retrieval (Dense & BM25)
        t0 = time.perf_counter()
        dense_top_k = settings.hybrid_dense_top_k
        bm25_top_k = settings.hybrid_bm25_top_k
        try:
            dense_results = self.dense_retriever.retrieve(
                query=query_str,
                top_k=dense_top_k,
                filters=req_filters,
            )
            bm25_results = self.bm25_retriever.retrieve(
                query=query_str,
                top_k=bm25_top_k,
                filters=req_filters,
            )
        except Exception as exc:
            logger.error("Retrieval stage failed: %s", exc)
            raise QueryPipelineError(f"Retrieval stage failed: {exc}") from exc
        latencies["retrieval_ms"] = (time.perf_counter() - t0) * 1000.0
        metadata["dense_candidates_count"] = len(dense_results)
        metadata["bm25_candidates_count"] = len(bm25_results)

        # Step 2: Reciprocal Rank Fusion (RRF)
        t1 = time.perf_counter()
        try:
            candidate_pool_limit = settings.hybrid_candidate_top_k
            fused_candidates = self.fuse(
                dense_results=dense_results,
                bm25_results=bm25_results,
                top_k=candidate_pool_limit,
            )
        except Exception as exc:
            logger.error("Fusion stage failed: %s", exc)
            raise QueryPipelineError(f"Fusion stage failed: {exc}") from exc
        latencies["fusion_ms"] = (time.perf_counter() - t1) * 1000.0
        metadata["fused_candidates_count"] = len(fused_candidates)

        # Step 3: Candidate Reranking
        t2 = time.perf_counter()
        rerank_top_k = req_top_k or settings.rerank_top_k
        try:
            reranked_results = self.rerank(
                query=query_str,
                candidates=fused_candidates,
                top_k=rerank_top_k,
            )
        except Exception as exc:
            logger.error("Reranking stage failed: %s", exc)
            raise QueryPipelineError(f"Reranking stage failed: {exc}") from exc
        latencies["reranking_ms"] = (time.perf_counter() - t2) * 1000.0
        metadata["reranked_candidates_count"] = len(reranked_results)

        # Step 4: Context Building & Token Budgeting
        t3 = time.perf_counter()
        try:
            built_context = self.build_context(reranked_results)
        except Exception as exc:
            logger.error("Context building failed: %s", exc)
            raise QueryPipelineError(f"Context building failed: {exc}") from exc
        latencies["context_building_ms"] = (time.perf_counter() - t3) * 1000.0
        metadata["context_token_count"] = built_context.token_count
        metadata["selected_chunks_count"] = len(built_context.selected_chunks)
        metadata["dropped_chunks_count"] = built_context.dropped_chunks_count

        # Step 5: Prompt Assembly
        t4 = time.perf_counter()
        try:
            prompt = self.build_prompt(
                query=query_str,
                built_context=built_context,
                version=req_version,
            )
        except Exception as exc:
            logger.error("Prompt assembly failed: %s", exc)
            raise QueryPipelineError(f"Prompt assembly failed: {exc}") from exc
        latencies["prompt_assembly_ms"] = (time.perf_counter() - t4) * 1000.0

        # Step 6: LLM Generation
        t5 = time.perf_counter()
        try:
            llm_response = self.generate(prompt)
        except Exception as exc:
            logger.error("LLM generation failed: %s", exc)
            raise QueryPipelineError(f"LLM generation failed: {exc}") from exc
        latencies["llm_generation_ms"] = (time.perf_counter() - t5) * 1000.0
        metadata["prompt_tokens"] = llm_response.prompt_tokens
        metadata["model_id"] = llm_response.model_id

        latencies["total_ms"] = (time.perf_counter() - t_total_start) * 1000.0

        # Step 7: Citation Verification & Attribution
        verified_citations, citation_validation = self.citation_mapper.map_to_context_citations(
            answer=llm_response.response_text,
            registry=built_context.citation_registry,
        )
        metadata["citation_validation"] = citation_validation.model_dump()
        if citation_validation.warnings:
            metadata["citation_warnings"] = citation_validation.warnings

        # Step 8: Citation Verification via CitationVerifier
        t6 = time.perf_counter()
        evidence_by_citation = {
            chunk.citation_id: chunk.content
            for chunk in built_context.selected_chunks
            if chunk.citation_id is not None
        }
        verification_result = self.citation_verifier.verify(
            answer=llm_response.response_text,
            citation_registry=built_context.citation_registry,
            evidence_by_citation=evidence_by_citation,
        )
        latencies["citation_verification_ms"] = (time.perf_counter() - t6) * 1000.0
        metadata["verification"] = verification_result.model_dump()
        metadata["verification_status"] = verification_result.overall_status.value

        # Step 9: Confidence Scoring
        t7 = time.perf_counter()
        confidence_signals = SignalExtractor.extract_signals(
            query=query_str,
            answer=llm_response.response_text,
            retrieval_candidates=fused_candidates,
            reranked_candidates=reranked_results,
            verification_result=verification_result,
            rrf_k=settings.rrf_k,
            num_sources=2,
        )
        confidence_result = self.confidence_calculator.calculate(
            signals=confidence_signals,
            metadata={"overall_status": verification_result.overall_status.value},
        )
        latencies["confidence_scoring_ms"] = (time.perf_counter() - t7) * 1000.0
        metadata["confidence"] = confidence_result.model_dump()

        latencies["total_ms"] = (time.perf_counter() - t_total_start) * 1000.0

        # Structured logging for observability (no secrets, no full text prompts)
        logger.info(
            "Confidence score: %.4f [band=%s] (retrieval=%.4f, reranking=%.4f, citation_support=%.4f, answerability=%.4f)",
            confidence_result.score,
            confidence_result.band.value,
            confidence_result.retrieval_signal,
            confidence_result.reranking_signal,
            confidence_result.citation_support_signal,
            confidence_result.answerability_signal,
        )


        return RAGResponse(
            query=query_str,
            answer=llm_response.response_text,
            citations=verified_citations,
            prompt_version=prompt.version.value,
            latency_breakdown_ms=latencies,
            metadata=metadata,
            verification=verification_result,
            confidence=confidence_result,
        )

    # -----------------------------------------------------------------------
    # Citation Attribution Helper
    # -----------------------------------------------------------------------

    def _verify_and_attribute_citations(
        self,
        answer: str,
        context_citations: list[Citation],
    ) -> list[Citation]:
        """
        Extract and verify citations present in the generated answer text.
        Delegates to CitationMapper for authoritative registry mapping.
        """
        registry = {c.citation_id: c for c in context_citations}
        verified, _ = self.citation_mapper.map_to_context_citations(
            answer=answer,
            registry=registry,
        )
        return verified


def create_rag_pipeline(
    in_memory: bool = False,
    vector_store: Optional[QdrantVectorStore] = None,
    embedding_service: Optional[EmbeddingService] = None,
    llm_provider: Optional[LLMProvider] = None,
    reranker: Optional[BaseReranker] = None,
    citation_mapper: Optional[CitationMapper] = None,
    citation_verifier: Optional[CitationVerifier] = None,
    confidence_calculator: Optional[ConfidenceCalculator] = None,
) -> RAGPipeline:
    """
    Factory function for creating a fully configured RAGPipeline.

    Args:
        in_memory: Use in-memory Qdrant instance.
        vector_store: Optional pre-configured vector store.
        embedding_service: Optional custom embedding service.
        llm_provider: Optional custom LLM provider.
        reranker: Optional custom reranker.
        citation_mapper: Optional custom citation mapper.
        citation_verifier: Optional custom citation verifier.
        confidence_calculator: Optional custom confidence calculator.

    Returns:
        Configured RAGPipeline instance.
    """
    return RAGPipeline(
        vector_store=vector_store,
        embedding_service=embedding_service,
        llm_provider=llm_provider,
        reranker=reranker,
        citation_mapper=citation_mapper,
        citation_verifier=citation_verifier,
        confidence_calculator=confidence_calculator,
        in_memory=in_memory,
    )
