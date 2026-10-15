-- V5__add_document_failure_and_retry.sql
-- Add failure_reason, retry_count, and queued_at for production document lifecycle tracking

ALTER TABLE documents ADD COLUMN IF NOT EXISTS failure_reason TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS retry_count INT DEFAULT 0 NOT NULL;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS queued_at TIMESTAMP WITH TIME ZONE;

-- Create index on retry_count for monitoring failed or stuck documents
CREATE INDEX IF NOT EXISTS idx_documents_retry_count ON documents (retry_count);
