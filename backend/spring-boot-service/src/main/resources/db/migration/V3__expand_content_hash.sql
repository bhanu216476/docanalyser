-- V3__expand_content_hash.sql
-- Expand content_hash column to accommodate SHA-256 hex digest with "sha256:" prefix.
-- Format stored: "sha256:" (7 chars) + 64 hex chars = 71 chars total.
-- Use 128 to allow for future algorithm prefixes without another migration.

ALTER TABLE documents ALTER COLUMN content_hash TYPE VARCHAR(128);
