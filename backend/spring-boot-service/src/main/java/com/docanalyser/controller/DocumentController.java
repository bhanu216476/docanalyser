package com.docanalyser.controller;

import com.docanalyser.entity.Document;
import com.docanalyser.redis.DocumentJobStatus;
import com.docanalyser.security.services.UserDetailsImpl;
import com.docanalyser.service.DocumentService;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

@RestController
@RequestMapping("/api/documents")
public class DocumentController {

    private final DocumentService documentService;

    public DocumentController(DocumentService documentService) {
        this.documentService = documentService;
    }

    @GetMapping
    public ResponseEntity<List<Document>> getDocuments(@AuthenticationPrincipal UserDetailsImpl userDetails) {
        if (userDetails == null) return ResponseEntity.status(401).build();
        return ResponseEntity.ok(documentService.getDocuments(userDetails));
    }

    @GetMapping("/{id}")
    public ResponseEntity<Document> getDocumentById(@PathVariable UUID id, @AuthenticationPrincipal UserDetailsImpl userDetails) {
        if (userDetails == null) return ResponseEntity.status(401).build();
        Optional<Document> document = documentService.getDocumentById(id, userDetails);
        return document.map(ResponseEntity::ok)
                .orElse(ResponseEntity.notFound().build());
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<?> deleteDocument(@PathVariable UUID id, @AuthenticationPrincipal UserDetailsImpl userDetails) {
        if (userDetails == null) return ResponseEntity.status(401).build();
        try {
            documentService.deleteDocument(id, userDetails);
            return ResponseEntity.ok().build();
        } catch (IllegalArgumentException e) {
            return ResponseEntity.status(403).body(Map.of("error", e.getMessage()));
        }
    }

    @GetMapping("/{id}/status")
    public ResponseEntity<?> getDocumentStatus(@PathVariable UUID id, @AuthenticationPrincipal UserDetailsImpl userDetails) {
        if (userDetails == null) return ResponseEntity.status(401).build();
        try {
            DocumentJobStatus status = documentService.getDocumentStatus(id, userDetails);
            return ResponseEntity.ok(status);
        } catch (IllegalArgumentException e) {
            return ResponseEntity.status(404).body(Map.of("error", e.getMessage()));
        }
    }

    @PostMapping("/{id}/retry")
    public ResponseEntity<?> retryDocument(@PathVariable UUID id, @AuthenticationPrincipal UserDetailsImpl userDetails) {
        if (userDetails == null) return ResponseEntity.status(401).build();
        try {
            DocumentJobStatus status = documentService.retryDocument(id, userDetails);
            return ResponseEntity.ok(status);
        } catch (IllegalStateException e) {
            return ResponseEntity.badRequest().body(Map.of("error", e.getMessage()));
        } catch (IllegalArgumentException e) {
            return ResponseEntity.status(404).body(Map.of("error", e.getMessage()));
        }
    }
}
