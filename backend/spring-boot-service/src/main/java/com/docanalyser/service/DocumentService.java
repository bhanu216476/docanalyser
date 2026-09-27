package com.docanalyser.service;

import com.docanalyser.dto.request.IngestionRequest;
import com.docanalyser.entity.Document;
import com.docanalyser.entity.DocumentStatus;
import com.docanalyser.redis.DocumentCacheService;
import com.docanalyser.redis.DocumentJobStatus;
import com.docanalyser.redis.DocumentJobStatusService;
import com.docanalyser.redis.DocumentStateMachine;
import com.docanalyser.repository.DocumentRepository;
import com.docanalyser.security.services.UserDetailsImpl;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Service
public class DocumentService {

    private static final Logger log = LoggerFactory.getLogger(DocumentService.class);

    private final DocumentRepository documentRepository;
    private final DocumentCacheService documentCacheService;
    private final DocumentJobStatusService documentJobStatusService;
    private final RagServiceClient ragServiceClient;

    @org.springframework.beans.factory.annotation.Autowired
    public DocumentService(DocumentRepository documentRepository,
                           DocumentCacheService documentCacheService,
                           DocumentJobStatusService documentJobStatusService,
                           RagServiceClient ragServiceClient) {
        this.documentRepository = documentRepository;
        this.documentCacheService = documentCacheService;
        this.documentJobStatusService = documentJobStatusService;
        this.ragServiceClient = ragServiceClient;
    }

    public DocumentService(DocumentRepository documentRepository) {
        this(documentRepository, null, null, null);
    }

    public List<Document> getDocuments(UserDetailsImpl userDetails) {
        boolean isAdmin = userDetails.getAuthorities().stream()
                .anyMatch(a -> a.getAuthority().equals("ROLE_ADMIN"));
        if (isAdmin) {
            return documentRepository.findAll();
        } else {
            return documentRepository.findByOwnerId(userDetails.getId());
        }
    }

    public Optional<Document> getDocumentById(UUID id, UserDetailsImpl userDetails) {
        boolean isAdmin = userDetails.getAuthorities().stream()
                .anyMatch(a -> a.getAuthority().equals("ROLE_ADMIN"));

        // Check Redis cache first
        if (documentCacheService != null) {
            Optional<Document> cached = documentCacheService.get(id);
            if (cached.isPresent()) {
                Document doc = cached.get();
                // Authorize access
                if (isAdmin || (doc.getOwner() != null && userDetails.getId().equals(doc.getOwner().getId()))) {
                    log.debug("Returning document {} from cache", id);
                    return Optional.of(doc);
                } else if (doc.getOwner() == null) {
                    // Document without owner (e.g. internal ingestion) accessible to admin or matching context
                    return Optional.of(doc);
                } else {
                    return Optional.empty();
                }
            }
        }

        // Cache miss: query PostgreSQL
        Optional<Document> document;
        if (isAdmin) {
            document = documentRepository.findById(id);
        } else {
            document = documentRepository.findByIdAndOwnerId(id, userDetails.getId());
        }

        // Populate cache on successful fetch
        if (document.isPresent() && documentCacheService != null) {
            documentCacheService.put(document.get());
        }

        return document;
    }

    public void deleteDocument(UUID id, UserDetailsImpl userDetails) {
        Optional<Document> doc = getDocumentById(id, userDetails);
        if (doc.isPresent()) {
            if (documentCacheService != null) {
                documentCacheService.evict(id);
            }
            documentRepository.delete(doc.get());
        } else {
            throw new IllegalArgumentException("Document not found or access denied");
        }
    }

    /**
     * Retrieves document processing job status.
     */
    public DocumentJobStatus getDocumentStatus(UUID id, UserDetailsImpl userDetails) {
        Document doc = getDocumentById(id, userDetails)
                .orElseThrow(() -> new IllegalArgumentException("Document not found or access denied"));

        if (documentJobStatusService != null) {
            DocumentJobStatus status = documentJobStatusService.getStatus(id);
            if (status != null) {
                return status;
            }
        }

        return DocumentJobStatus.fromDocument(doc);
    }

    /**
     * Retries ingestion for a document currently in FAILED state.
     */
    public DocumentJobStatus retryDocument(UUID id, UserDetailsImpl userDetails) {
        Document doc = getDocumentById(id, userDetails)
                .orElseThrow(() -> new IllegalArgumentException("Document not found or access denied"));

        if (doc.getStatus() != DocumentStatus.FAILED) {
            throw new IllegalStateException(
                String.format("Document is in status %s and cannot be retried. Only FAILED documents can be retried.", doc.getStatus())
            );
        }

        // State Machine transition FAILED -> PROCESSING
        DocumentStateMachine.validateTransition(doc.getStatus(), DocumentStatus.PROCESSING);

        doc.setStatus(DocumentStatus.PROCESSING);
        documentRepository.save(doc);

        if (documentJobStatusService != null) {
            documentJobStatusService.setStatus(id, DocumentStatus.PROCESSING, null);
        }
        if (documentCacheService != null) {
            documentCacheService.evict(id);
        }

        if (ragServiceClient != null) {
            try {
                IngestionRequest request = new IngestionRequest();
                request.setDocumentId(doc.getId().toString());
                request.setFileName(doc.getFileName());
                request.setSource(doc.getSource());
                request.setFileUrl(doc.getSource());

                ragServiceClient.ingestDocument(request);

                // Transition PROCESSING -> INDEXED
                DocumentStateMachine.validateTransition(DocumentStatus.PROCESSING, DocumentStatus.INDEXED);
                doc.setStatus(DocumentStatus.INDEXED);
                documentRepository.save(doc);

                if (documentJobStatusService != null) {
                    return documentJobStatusService.setStatus(id, DocumentStatus.INDEXED, null);
                }
            } catch (Exception e) {
                String errorMsg = e.getMessage() != null ? e.getMessage() : "Ingestion retry failed";
                log.error("Retry failed for document {}: {}", id, errorMsg);

                doc.setStatus(DocumentStatus.FAILED);
                documentRepository.save(doc);

                if (documentJobStatusService != null) {
                    return documentJobStatusService.setStatus(id, DocumentStatus.FAILED, errorMsg);
                }
            }
        }

        return DocumentJobStatus.fromDocument(doc);
    }
}
