package com.docanalyser.repository;

import com.docanalyser.entity.Document;
import com.docanalyser.entity.DocumentStatus;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

/**
 * Spring Data JPA repository providing CRUD and query operations for {@link Document}.
 */
@Repository
public interface DocumentRepository extends JpaRepository<Document, UUID> {

    /**
     * Find a document record by its SHA-256 content hash (useful for deduplication).
     *
     * @param contentHash SHA-256 hash string.
     * @return Optional containing the matching document if present.
     */
    Optional<Document> findByContentHash(String contentHash);

    /**
     * Find all documents matching a specific lifecycle status.
     *
     * @param status The document status.
     * @return List of matching documents.
     */
    List<Document> findByStatus(DocumentStatus status);
}
