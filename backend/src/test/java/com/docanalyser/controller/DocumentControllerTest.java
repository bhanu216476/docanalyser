package com.docanalyser.controller;

import com.docanalyser.entity.Document;
import com.docanalyser.entity.DocumentStatus;
import com.docanalyser.redis.DocumentJobStatus;
import com.docanalyser.security.services.UserDetailsImpl;
import com.docanalyser.service.DocumentService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.authority.SimpleGrantedAuthority;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class DocumentControllerTest {

    @Mock
    private DocumentService documentService;

    @InjectMocks
    private DocumentController documentController;

    private UserDetailsImpl userDetails;
    private UUID docId;
    private Document document;

    @BeforeEach
    void setUp() {
        UUID userId = UUID.randomUUID();
        docId = UUID.randomUUID();
        userDetails = new UserDetailsImpl(
                userId, "User", "user@example.com", "hash",
                List.of(new SimpleGrantedAuthority("ROLE_USER")), true
        );
        document = new Document("file.pdf", "pdf", "application/pdf", "source", 100L, "hash");
        document.setId(docId);
    }

    @Test
    @DisplayName("GET /api/documents returns documents list")
    void getDocuments_returnsList() {
        when(documentService.getDocuments(userDetails)).thenReturn(List.of(document));

        ResponseEntity<List<Document>> response = documentController.getDocuments(userDetails);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(response.getBody()).hasSize(1);
    }

    @Test
    @DisplayName("GET /api/documents/{id} returns document when found")
    void getDocumentById_found_returnsOk() {
        when(documentService.getDocumentById(docId, userDetails)).thenReturn(Optional.of(document));

        ResponseEntity<Document> response = documentController.getDocumentById(docId, userDetails);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(response.getBody()).isNotNull();
        assertThat(response.getBody().getId()).isEqualTo(docId);
    }

    @Test
    @DisplayName("GET /api/documents/{id}/status returns job status")
    void getDocumentStatus_returnsStatus() {
        DocumentJobStatus jobStatus = new DocumentJobStatus(
                "job-123", docId, DocumentStatus.PROCESSING, Instant.now(), Instant.now(), null
        );
        when(documentService.getDocumentStatus(docId, userDetails)).thenReturn(jobStatus);

        ResponseEntity<?> response = documentController.getDocumentStatus(docId, userDetails);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(response.getBody()).isEqualTo(jobStatus);
    }

    @Test
    @DisplayName("GET /api/documents/{id}/status returns 404 when document not found")
    void getDocumentStatus_notFound_returns404() {
        when(documentService.getDocumentStatus(docId, userDetails))
                .thenThrow(new IllegalArgumentException("Document not found"));

        ResponseEntity<?> response = documentController.getDocumentStatus(docId, userDetails);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);
    }

    @Test
    @DisplayName("POST /api/documents/{id}/retry returns updated status on success")
    void retryDocument_success_returnsOk() {
        DocumentJobStatus retriedStatus = new DocumentJobStatus(
                "job-123", docId, DocumentStatus.INDEXED, Instant.now(), Instant.now(), null
        );
        when(documentService.retryDocument(docId, userDetails)).thenReturn(retriedStatus);

        ResponseEntity<?> response = documentController.retryDocument(docId, userDetails);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(response.getBody()).isEqualTo(retriedStatus);
    }

    @Test
    @DisplayName("POST /api/documents/{id}/retry returns 400 when document cannot be retried")
    void retryDocument_invalidState_returnsBadRequest() {
        when(documentService.retryDocument(docId, userDetails))
                .thenThrow(new IllegalStateException("Only FAILED documents can be retried"));

        ResponseEntity<?> response = documentController.retryDocument(docId, userDetails);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.BAD_REQUEST);
        Map<?, ?> body = (Map<?, ?>) response.getBody();
        assertThat(body).isNotNull();
        assertThat(body.get("error")).isEqualTo("Only FAILED documents can be retried");
    }

    @Test
    @DisplayName("DELETE /api/documents/{id} returns 200 on success")
    void deleteDocument_success_returnsOk() {
        ResponseEntity<?> response = documentController.deleteDocument(docId, userDetails);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        verify(documentService).deleteDocument(docId, userDetails);
    }
}
