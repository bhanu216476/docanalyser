package com.docanalyser.redis;

import com.docanalyser.entity.Document;
import com.docanalyser.entity.DocumentStatus;
import com.docanalyser.repository.DocumentRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.TimeUnit;

/**
 * Service managing document processing job status with Redis and PostgreSQL fallback.
 */
@Service
public class DocumentJobStatusService {

    private static final Logger log = LoggerFactory.getLogger(DocumentJobStatusService.class);

    private final RedisTemplate<String, Object> redisTemplate;
    private final DocumentRepository documentRepository;

    @Value("${app.redis.job-status-ttl-seconds:86400}")
    private long jobStatusTtlSeconds;

    public DocumentJobStatusService(RedisTemplate<String, Object> redisTemplate,
                                    DocumentRepository documentRepository) {
        this.redisTemplate = redisTemplate;
        this.documentRepository = documentRepository;
    }

    /**
     * Initializes or records a new status for a document.
     */
    public DocumentJobStatus setStatus(UUID documentId, DocumentStatus status, String errorMessage) {
        if (documentId == null) {
            throw new IllegalArgumentException("documentId cannot be null");
        }

        DocumentJobStatus existing = getStatus(documentId);
        DocumentStatus currentStatus = existing != null ? existing.getStatus() : null;

        // Concurrency / Race Condition safeguard:
        // If document is already INDEXED (or READY/PROCESSED), do not allow FAILED or PROCESSING to overwrite it
        if ((currentStatus == DocumentStatus.INDEXED || currentStatus == DocumentStatus.READY || currentStatus == DocumentStatus.PROCESSED)
                && (status == DocumentStatus.PROCESSING || status == DocumentStatus.FAILED)) {
            log.warn("Ignoring race update: Document {} is already {} - rejecting transition to {}",
                    documentId, currentStatus, status);
            return existing;
        }

        // Validate state machine transition
        DocumentStateMachine.validateTransition(currentStatus, status);

        Instant now = Instant.now();
        Instant startedAt = (existing != null && existing.getStartedAt() != null) ? existing.getStartedAt() : now;
        String jobId = (existing != null && existing.getJobId() != null) ? existing.getJobId() : UUID.randomUUID().toString();

        DocumentJobStatus jobStatus = new DocumentJobStatus(
                jobId,
                documentId,
                status,
                startedAt,
                now,
                errorMessage
        );

        saveToRedis(jobStatus);
        return jobStatus;
    }

    /**
     * Retrieves the current document job status.
     * Looks up Redis first; if missing or Redis is unavailable, falls back to PostgreSQL.
     */
    public DocumentJobStatus getStatus(UUID documentId) {
        if (documentId == null) return null;

        String key = RedisKeys.documentStatusKey(documentId);
        try {
            Object obj = redisTemplate.opsForValue().get(key);
            if (obj instanceof DocumentJobStatus status) {
                return status;
            }
        } catch (Exception e) {
            log.warn("Redis unavailable while reading status for document {}: {}", documentId, e.getMessage());
        }

        // Fallback to PostgreSQL
        Optional<Document> docOpt = documentRepository.findById(documentId);
        if (docOpt.isPresent()) {
            Document doc = docOpt.get();
            DocumentJobStatus fallback = DocumentJobStatus.fromDocument(doc);
            // Attempt to populate Redis in the background
            saveToRedis(fallback);
            return fallback;
        }

        return null;
    }

    private void saveToRedis(DocumentJobStatus status) {
        if (status == null || status.getDocumentId() == null) return;
        String key = RedisKeys.documentStatusKey(status.getDocumentId());
        try {
            redisTemplate.opsForValue().set(key, status, jobStatusTtlSeconds, TimeUnit.SECONDS);
        } catch (Exception e) {
            log.warn("Redis unavailable while saving status for document {}: {}", status.getDocumentId(), e.getMessage());
        }
    }
}
