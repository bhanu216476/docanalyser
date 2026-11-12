"""
Tests for Advanced Query Intelligence in DocAnalyser RAG Platform.
"""

from app.query.classifier import QueryIntentClassifier
from app.query.intelligence import QueryIntelligenceService
from app.query.models import QueryIntent
from app.query.rewriter import QueryRewriter


def test_intent_classification():
    classifier = QueryIntentClassifier()

    # Greetings
    assert classifier.classify("Hello there") == QueryIntent.CONVERSATIONAL
    assert classifier.classify("Hi Maddy") == QueryIntent.CONVERSATIONAL

    # Comparisons
    assert classifier.classify("Compare PostgreSQL versus MySQL in terms of performance") == QueryIntent.COMPARISON
    assert classifier.classify("What is the difference between dense and sparse retrieval?") == QueryIntent.COMPARISON

    # Summaries
    assert classifier.classify("Give me a high-level overview and summary of this document") == QueryIntent.SUMMARY
    assert classifier.classify("TLDR of the security policy") == QueryIntent.SUMMARY

    # Exploration / Quiz
    assert classifier.classify("Generate 5 questions to test comprehension of this document") == QueryIntent.EXPLORATION
    assert classifier.classify("Create a quiz for me based on this chapter") == QueryIntent.EXPLORATION

    # Conceptual
    assert classifier.classify("Explain the architecture of the hybrid RAG system") == QueryIntent.CONCEPTUAL

    # Factual
    assert classifier.classify("What is the maximum token limit?") == QueryIntent.FACTUAL


def test_query_rewriting_pronoun_resolution():
    rewriter = QueryRewriter()

    history = [
        {"role": "user", "content": "What is PostgreSQL?"},
        {"role": "assistant", "content": "PostgreSQL is an advanced open-source relational database."},
    ]

    # Follow-up with pronoun "its"
    rewritten, is_follow_up, entities = rewriter.rewrite_with_context("What are its advantages?", history)
    assert is_follow_up is True
    assert "postgresql" in rewritten.lower()

    # Self-contained query should not be rewritten
    query = "What is the token limit of OpenAI embeddings?"
    standalone, is_follow_up, _ = rewriter.rewrite_with_context(query, history)
    assert is_follow_up is False
    assert standalone == query


def test_query_decomposition():
    rewriter = QueryRewriter()
    composite_query = "Explain the architecture of this system and compare it with the previous version"
    subqueries = rewriter.decompose(composite_query, QueryIntent.MULTI_PART)

    assert len(subqueries) >= 2
    assert any("architecture" in sq.lower() for sq in subqueries)
    assert any("compare" in sq.lower() or "previous version" in sq.lower() for sq in subqueries)


def test_unified_query_intelligence_service():
    service = QueryIntelligenceService()

    history = [
        {"role": "user", "content": "What is Qdrant?"},
        {"role": "assistant", "content": "Qdrant is a vector similarity search engine."},
    ]

    analysis = service.analyze("What are its main features?", history)
    assert analysis.is_follow_up is True
    assert analysis.requires_retrieval is True
    assert "qdrant" in analysis.rewritten_query.lower()
    assert analysis.recommended_top_k >= 5
