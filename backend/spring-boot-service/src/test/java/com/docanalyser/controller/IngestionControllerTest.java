package com.docanalyser.controller;

import com.docanalyser.dto.request.IngestionRequest;
import com.docanalyser.entity.Document;
import com.docanalyser.entity.DocumentStatus;
import com.docanalyser.redis.DocumentCacheService;
import com.docanalyser.redis.DocumentJobStatusService;
import com.docanalyser.repository.DocumentRepository;
import com.docanalyser.service.RagServiceClient;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;

import java.util.Map;
import java.util.Optional;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class IngestionControllerTest {

    @Mock
    private RagServiceClient ragServiceClient;

    @Mock
    private DocumentRepository documentRepository;

    @Mock
    private DocumentJobStatusService documentJobStatusService;

    @Mock
    private DocumentCacheService documentCacheService;

    @InjectMocks
    private IngestionController ingestionController;

    private UUID docId;
    private IngestionRequest request;
    private Document document;

    @BeforeEach
    void setUp() {
        docId = UUID.randomUUID();
        request = new IngestionRequest();
        request.setDocumentId(docId.toString());
        request.setFileName("manual.pdf");
        request.setSource("google-drive");
        request.setFileUrl("https://example.com/manual.pdf");

        document = new Document("manual.pdf", "pdf", "application/pdf", "google-drive", 100L, "hash");
        document.setId(docId);
    }

    @Test
    @DisplayName("ingestDocument executes full state machine lifecycle and transitions to INDEXED on success")
    void ingestDocument_success_transitionsToIndexed() {
        when(documentRepository.findById(docId)).thenReturn(Optional.of(document));
        when(documentRepository.save(any(Document.class))).thenAnswer(i -> i.getArgument(0));
        when(ragServiceClient.ingestDocument(request)).thenReturn(Map.of("chunks", 12, "vectors", 12));

        ResponseEntity<?> response = ingestionController.ingestDocument(request);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.ACCEPTED);
        Map<?, ?> body = (Map<?, ?>) response.getBody();
        assertThat(body).isNotNull();
        assertThat(body.get("status")).isEqualTo(DocumentStatus.INDEXED.name());

        verify(documentJobStatusService).setStatus(eq(docId), eq(DocumentStatus.UPLOADED), any());
        verify(documentJobStatusService).setStatus(eq(docId), eq(DocumentStatus.PROCESSING), any());
        verify(documentJobStatusService).setStatus(eq(docId), eq(DocumentStatus.INDEXED), any());
        verify(documentCacheService, org.mockito.Mockito.times(2)).evict(docId);
    }

    @Test
    @DisplayName("ingestDocument transitions to FAILED and returns 502 on Python RAG error")
    void ingestDocument_failure_transitionsToFailed() {
        when(documentRepository.findById(docId)).thenReturn(Optional.of(document));
        when(documentRepository.save(any(Document.class))).thenAnswer(i -> i.getArgument(0));
        when(ragServiceClient.ingestDocument(request)).thenThrow(new RuntimeException("Embedding service offline"));

        ResponseEntity<?> response = ingestionController.ingestDocument(request);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.BAD_GATEWAY);
        Map<?, ?> body = (Map<?, ?>) response.getBody();
        assertThat(body).isNotNull();
        assertThat(body.get("status")).isEqualTo(DocumentStatus.FAILED.name());
        assertThat(body.get("error")).toString().contains("Embedding service offline");

        verify(documentJobStatusService).setStatus(eq(docId), eq(DocumentStatus.FAILED), any());
    }
}
