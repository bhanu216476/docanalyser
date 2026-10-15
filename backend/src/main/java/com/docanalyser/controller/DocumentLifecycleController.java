package com.docanalyser.controller;

import com.docanalyser.auth.RagServiceException;
import com.docanalyser.client.RagServiceClient;
import com.docanalyser.dto.request.DocumentLifecycleRequest;
import com.docanalyser.dto.request.DocumentLifecycleRequest.DocumentEvent;
import com.docanalyser.dto.response.DocumentLifecycleResponse;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/api/v1/documents")
public class DocumentLifecycleController {
    private final RagServiceClient ragServiceClient;

    public DocumentLifecycleController(RagServiceClient ragServiceClient) {
        this.ragServiceClient = ragServiceClient;
    }

    @PostMapping
    public ResponseEntity<DocumentLifecycleResponse> processDocument(
            @Valid @RequestBody DocumentLifecycleRequest request
    ) {
        validateEventFields(request);
        return ResponseEntity.ok(ragServiceClient.processDocument(request));
    }

    @ExceptionHandler(RagServiceException.class)
    public ResponseEntity<Map<String, String>> handleRagServiceError(RagServiceException exception) {
        return ResponseEntity.status(exception.getStatusCode())
                .body(Map.of("error", exception.getMessage()));
    }

    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<Map<String, String>> handleInvalidLifecycleRequest(IllegalArgumentException exception) {
        return ResponseEntity.badRequest().body(Map.of("error", exception.getMessage()));
    }

    private void validateEventFields(DocumentLifecycleRequest request) {
        if (request.event() != DocumentEvent.DOCUMENT_DELETED
                && (request.fileName() == null || request.fileName().isBlank()
                || request.sourceUrl() == null || request.sourceUrl().isBlank())) {
            throw new IllegalArgumentException("fileName and sourceUrl are required for add/update events");
        }
    }
}