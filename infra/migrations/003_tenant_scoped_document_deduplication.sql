-- Scope document content deduplication to the owning client.
-- The original global UNIQUE(content_hash) prevented separate tenants from
-- ingesting identical content and did not match tenant-scoped duplicate lookups.

ALTER TABLE documents
    DROP CONSTRAINT IF EXISTS documents_content_hash_key;

CREATE UNIQUE INDEX IF NOT EXISTS documents_client_content_hash_uidx
    ON documents ((metadata->>'client_id'), content_hash);
