package com.docanalyser.redis;

import com.docanalyser.entity.Document;
import com.docanalyser.entity.DocumentStatus;
import com.docanalyser.repository.DocumentRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.redis.RedisConnectionFailureException;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.data.redis.core.ValueOperations;

import java.time.Instant;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.TimeUnit;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class DocumentJobStatusServiceTest {

    @Mock
    private RedisTemplate<String, Object> redisTemplate;

    @Mock
    private ValueOperations<String, Object> valueOperations;

    @Mock
    private DocumentRepository documentRepository;

    @InjectMocks
    private DocumentJobStatusService statusService;

    private UUID docId;
    private String statusKey;

    @BeforeEach
    void setUp() {
        docId = UUID.randomUUID();
        statusKey = RedisKeys.documentStatusKey(docId);
        when(redisTemplate.opsForValue()).thenReturn(valueOperations);
    }

    @Test
    @DisplayName("setStatus stores UPLOADED status into Redis")
    void setStatus_uploaded_storesInRedis() {
        when(valueOperations.get(statusKey)).thenReturn(null);
        when(documentRepository.findById(docId)).thenReturn(Optional.empty());

        DocumentJobStatus result = statusService.setStatus(docId, DocumentStatus.UPLOADED, null);

        assertThat(result).isNotNull();
        assertThat(result.getDocumentId()).isEqualTo(docId);
        assertThat(result.getStatus()).isEqualTo(DocumentStatus.UPLOADED);
        verify(valueOperations).set(eq(statusKey), any(DocumentJobStatus.class), anyLong(), eq(TimeUnit.SECONDS));
    }

    @Test
    @DisplayName("getStatus returns status from Redis on hit")
    void getStatus_cacheHit_returnsRedisStatus() {
        DocumentJobStatus cached = new DocumentJobStatus(
                "job-1", docId, DocumentStatus.PROCESSING, Instant.now(), Instant.now(), null
        );
        when(valueOperations.get(statusKey)).thenReturn(cached);

        DocumentJobStatus result = statusService.getStatus(docId);

        assertThat(result).isNotNull();
        assertThat(result.getStatus()).isEqualTo(DocumentStatus.PROCESSING);
        verify(documentRepository, never()).findById(any());
    }

    @Test
    @DisplayName("getStatus falls back to PostgreSQL when Redis has no record")
    void getStatus_redisMiss_fallsBackToPostgres() {
        when(valueOperations.get(statusKey)).thenReturn(null);

        Document doc = new Document("file.pdf", "pdf", "application/pdf", "source", 100L, "hash");
        doc.setId(docId);
        doc.setStatus(DocumentStatus.INDEXED);
        when(documentRepository.findById(docId)).thenReturn(Optional.of(doc));

        DocumentJobStatus result = statusService.getStatus(docId);

        assertThat(result).isNotNull();
        assertThat(result.getStatus()).isEqualTo(DocumentStatus.INDEXED);
        verify(documentRepository).findById(docId);
    }

    @Test
    @DisplayName("getStatus gracefully falls back to PostgreSQL when Redis throws exception")
    void getStatus_redisFailure_fallsBackToPostgres() {
        when(valueOperations.get(statusKey)).thenThrow(new RedisConnectionFailureException("Redis connection refused"));

        Document doc = new Document("file.pdf", "pdf", "application/pdf", "source", 100L, "hash");
        doc.setId(docId);
        doc.setStatus(DocumentStatus.FAILED);
        when(documentRepository.findById(docId)).thenReturn(Optional.of(doc));

        DocumentJobStatus result = statusService.getStatus(docId);

        assertThat(result).isNotNull();
        assertThat(result.getStatus()).isEqualTo(DocumentStatus.FAILED);
    }

    @Test
    @DisplayName("Race condition safeguard: INDEXED document rejects transition to FAILED or PROCESSING")
    void raceCondition_indexedDocumentRejectsOlderFailure() {
        DocumentJobStatus indexedStatus = new DocumentJobStatus(
                "job-1", docId, DocumentStatus.INDEXED, Instant.now(), Instant.now(), null
        );
        when(valueOperations.get(statusKey)).thenReturn(indexedStatus);

        DocumentJobStatus result = statusService.setStatus(docId, DocumentStatus.FAILED, "Late error from slow worker");

        assertThat(result.getStatus()).isEqualTo(DocumentStatus.INDEXED);
        // Verify set was NOT called with FAILED
        verify(valueOperations, never()).set(eq(statusKey), any(DocumentJobStatus.class), anyLong(), eq(TimeUnit.SECONDS));
    }

    @Test
    @DisplayName("Invalid transition from UPLOADED directly to INDEXED throws IllegalStateException")
    void invalidTransition_throwsIllegalStateException() {
        DocumentJobStatus uploadedStatus = new DocumentJobStatus(
                "job-1", docId, DocumentStatus.UPLOADED, Instant.now(), Instant.now(), null
        );
        when(valueOperations.get(statusKey)).thenReturn(uploadedStatus);

        assertThatThrownBy(() -> statusService.setStatus(docId, DocumentStatus.INDEXED, null))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("Invalid document status transition");
    }
}
