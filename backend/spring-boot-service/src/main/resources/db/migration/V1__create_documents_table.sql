-- V1__create_documents_table.sql
-- Document metadata persistence schema for DocAnalyser RAG pipeline

CREATE TABLE IF NOT EXISTS documents (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    file_name VARCHAR(255) NOT NULL,
    file_type VARCHAR(50) NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    source TEXT NOT NULL,
    file_size BIGINT NOT NULL CHECK (file_size >= 0),
    content_hash VARCHAR(64) NOT NULL,
    status VARCHAR(20) DEFAULT 'PENDING' NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Index on content_hash for deduplication and content-addressed lookups
CREATE INDEX IF NOT EXISTS idx_documents_content_hash ON documents (content_hash);

-- Index on status for pipeline processing state queries
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents (status);
