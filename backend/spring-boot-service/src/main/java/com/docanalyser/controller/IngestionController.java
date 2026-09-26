package com.docanalyser.controller;

import com.docanalyser.dto.request.IngestionRequest;
import com.docanalyser.entity.Document;
import com.docanalyser.entity.DocumentStatus;
import com.docanalyser.redis.DocumentCacheService;
import com.docanalyser.redis.DocumentJobStatusService;
import com.docanalyser.redis.DocumentStateMachine;
import com.docanalyser.repository.DocumentRepository;
import com.docanalyser.service.RagServiceClient;
import jakarta.validation.Valid;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;
import java.util.Optional;
import java.util.UUID;

/**
 * Internal ingestion endpoint called by n8n workflow.
 * Manages full lifecycle state transitions:
 * UPLOADED -> PROCESSING -> INDEXED (or FAILED)
 */
@RestController
@RequestMapping("/api/internal/documents")
public class IngestionController {

    private static final Logger log = LoggerFactory.getLogger(IngestionController.class);

    private final RagServiceClient ragServiceClient;
    private final DocumentRepository documentRepository;
    private final DocumentJobStatusService documentJobStatusService;
    private final DocumentCacheService documentCacheService;

    @org.springframework.beans.factory.annotation.Autowired
    public IngestionController(RagServiceClient ragServiceClient,
                               DocumentRepository documentRepository,
                               DocumentJobStatusService documentJobStatusService,
                               DocumentCacheService documentCacheService) {
        this.ragServiceClient = ragServiceClient;
        this.documentRepository = documentRepository;
        this.documentJobStatusService = documentJobStatusService;
        this.documentCacheService = documentCacheService;
    }

    public IngestionController(RagServiceClient ragServiceClient) {
        this(ragServiceClient, null, null, null);
    }

    @PostMapping("/ingest")
    public ResponseEntity<?> ingestDocument(@Valid @RequestBody IngestionRequest request) {
        UUID docId;
        try {
            docId = request.getDocumentId() != null ? UUID.fromString(request.getDocumentId()) : UUID.randomUUID();
        } catch (IllegalArgumentException e) {
            docId = UUID.randomUUID();
        }

        Document document = null;
        if (documentRepository != null) {
            Optional<Document> existing = documentRepository.findById(docId);
            if (existing.isPresent()) {
                document = existing.get();
                if (document.getStatus() == DocumentStatus.INDEXED || document.getStatus() == DocumentStatus.READY) {
                    return ResponseEntity.ok(Map.of(
                            "documentId", document.getId().toString(),
                            "status", document.getStatus().name(),
                            "message", "Document already indexed"
                    ));
                }
            } else {
                String fileName = request.getFileName() != null ? request.getFileName() : "unknown";
                String fileType = fileName.contains(".") ? fileName.substring(fileName.lastIndexOf('.') + 1) : "unknown";
                document = new Document(
                        fileName,
                        fileType,
                        "application/octet-stream",
                        request.getSource() != null ? request.getSource() : "internal",
                        0L,
                        "hash:" + docId,
                        DocumentStatus.UPLOADED
                );
                document.setId(docId);
                document = documentRepository.save(document);
            }
        }

        // Step 1: Record UPLOADED state in Redis
        if (documentJobStatusService != null) {
            documentJobStatusService.setStatus(docId, DocumentStatus.UPLOADED, null);
        }

        // Step 2: Transition UPLOADED -> PROCESSING
        DocumentStateMachine.validateTransition(DocumentStatus.UPLOADED, DocumentStatus.PROCESSING);
        if (document != null) {
            document.setStatus(DocumentStatus.PROCESSING);
            documentRepository.save(document);
        }
        if (documentJobStatusService != null) {
            documentJobStatusService.setStatus(docId, DocumentStatus.PROCESSING, null);
        }
        if (documentCacheService != null) {
            documentCacheService.evict(docId);
        }

        // Step 3: Invoke Python RAG ingestion
        try {
            Map<String, Object> response = ragServiceClient.ingestDocument(request);

            // Step 4: Successful indexing -> PROCESSING -> INDEXED
            DocumentStateMachine.validateTransition(DocumentStatus.PROCESSING, DocumentStatus.INDEXED);
            if (document != null) {
                document.setStatus(DocumentStatus.INDEXED);
                documentRepository.save(document);
            }
            if (documentJobStatusService != null) {
                documentJobStatusService.setStatus(docId, DocumentStatus.INDEXED, null);
            }
            if (documentCacheService != null) {
                documentCacheService.evict(docId);
            }

            return ResponseEntity.accepted().body(Map.of(
                    "documentId", docId.toString(),
                    "status", DocumentStatus.INDEXED.name(),
                    "details", response
            ));
        } catch (Exception e) {
            String errorMsg = e.getMessage() != null ? e.getMessage() : "Ingestion failed";
            log.error("Ingestion failed for document {}: {}", docId, errorMsg);

            // Step 5: Failure -> PROCESSING -> FAILED
            if (document != null) {
                document.setStatus(DocumentStatus.FAILED);
                documentRepository.save(document);
            }
            if (documentJobStatusService != null) {
                documentJobStatusService.setStatus(docId, DocumentStatus.FAILED, errorMsg);
            }
            if (documentCacheService != null) {
                documentCacheService.evict(docId);
            }

            return ResponseEntity.status(502).body(Map.of(
                    "documentId", docId.toString(),
                    "status", DocumentStatus.FAILED.name(),
                    "error", errorMsg
            ));
        }
    }
}
