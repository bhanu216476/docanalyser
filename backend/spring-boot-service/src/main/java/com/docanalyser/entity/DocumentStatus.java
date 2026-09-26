package com.docanalyser.entity;

/**
 * Controlled set of lifecycle states for a document in the ingestion pipeline.
 */
public enum DocumentStatus {
    /** Document metadata registered, awaiting processing. */
    PENDING,
    /** Document uploaded by client/n8n, queued for processing. */
    UPLOADED,
    /** Document is actively being chunked, embedded, and indexed. */
    PROCESSING,
    /** Document successfully ingested, chunked, and indexed — ready for retrieval. */
    READY,
    /** Document successfully ingested (legacy alias for READY). */
    PROCESSED,
    /** Document successfully chunked, embedded, and indexed into vector store. */
    INDEXED,
    /** Ingestion or downstream pipeline step encountered an unrecoverable failure. */
    FAILED
}
