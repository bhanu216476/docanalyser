package com.docanalyser.entity;

/**
 * Controlled set of lifecycle states for a document in the ingestion pipeline.
 */
public enum DocumentStatus {
    /** Document metadata registered, awaiting chunking and vector processing. */
    PENDING,
    /** Document successfully ingested, chunked, and indexed. */
    PROCESSED,
    /** Ingestion or downstream pipeline step encountered an unrecoverable failure. */
    FAILED
}
