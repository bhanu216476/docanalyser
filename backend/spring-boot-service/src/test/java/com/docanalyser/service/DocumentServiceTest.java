package com.docanalyser.service;

import com.docanalyser.entity.Document;
import com.docanalyser.entity.DocumentStatus;
import com.docanalyser.repository.DocumentRepository;
import com.docanalyser.security.services.UserDetailsImpl;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class DocumentServiceTest {

    @Mock
    private DocumentRepository documentRepository;

    @Mock
    private com.docanalyser.redis.DocumentCacheService documentCacheService;

    @Mock
    private com.docanalyser.redis.DocumentJobStatusService documentJobStatusService;

    @Mock
    private RagServiceClient ragServiceClient;

    @InjectMocks
    private DocumentService documentService;

    private UUID ownerId;
    private UUID otherUserId;
    private UUID adminId;
    private UserDetailsImpl userDetails;
    private UserDetailsImpl otherUserDetails;
    private UserDetailsImpl adminDetails;
    private Document userDoc;
    private UUID docId;

    @BeforeEach
    void setUp() {
        ownerId = UUID.randomUUID();
        otherUserId = UUID.randomUUID();
        adminId = UUID.randomUUID();
        docId = UUID.randomUUID();

        List<GrantedAuthority> userAuthorities = List.of(new SimpleGrantedAuthority("ROLE_USER"));
        List<GrantedAuthority> adminAuthorities = List.of(new SimpleGrantedAuthority("ROLE_ADMIN"));

        userDetails = new UserDetailsImpl(ownerId, "User", "user@example.com", "hash", userAuthorities, true);
        otherUserDetails = new UserDetailsImpl(otherUserId, "Other", "other@example.com", "hash", userAuthorities, true);
        adminDetails = new UserDetailsImpl(adminId, "Admin", "admin@example.com", "hash", adminAuthorities, true);

        userDoc = new Document("test.pdf", "pdf", "application/pdf", "google-drive", 1024L, "abc123");
        userDoc.setId(docId);
    }

    @Test
    void getDocuments_normalUser_returnsOwnDocuments() {
        when(documentRepository.findByOwnerId(ownerId)).thenReturn(List.of(userDoc));

        List<Document> docs = documentService.getDocuments(userDetails);

        assertThat(docs).hasSize(1);
        verify(documentRepository).findByOwnerId(ownerId);
    }

    @Test
    void getDocuments_admin_returnsAllDocuments() {
        when(documentRepository.findAll()).thenReturn(List.of(userDoc));

        List<Document> docs = documentService.getDocuments(adminDetails);

        assertThat(docs).hasSize(1);
        verify(documentRepository).findAll();
    }

    @Test
    void getDocumentById_owner_returnsDocument() {
        when(documentRepository.findByIdAndOwnerId(docId, ownerId)).thenReturn(Optional.of(userDoc));

        Optional<Document> doc = documentService.getDocumentById(docId, userDetails);

        assertThat(doc).isPresent();
    }

    @Test
    void getDocumentById_otherUser_returnsEmpty() {
        when(documentRepository.findByIdAndOwnerId(docId, otherUserId)).thenReturn(Optional.empty());

        Optional<Document> doc = documentService.getDocumentById(docId, otherUserDetails);

        assertThat(doc).isEmpty();
    }

    @Test
    void getDocumentById_admin_canAccessAnyDocument() {
        when(documentRepository.findById(docId)).thenReturn(Optional.of(userDoc));

        Optional<Document> doc = documentService.getDocumentById(docId, adminDetails);

        assertThat(doc).isPresent();
    }

    @Test
    void deleteDocument_owner_deletesSuccessfully() {
        when(documentRepository.findByIdAndOwnerId(docId, ownerId)).thenReturn(Optional.of(userDoc));

        documentService.deleteDocument(docId, userDetails);

        verify(documentRepository).delete(userDoc);
    }

    @Test
    void deleteDocument_otherUser_throwsException() {
        when(documentRepository.findByIdAndOwnerId(docId, otherUserId)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> documentService.deleteDocument(docId, otherUserDetails))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("not found or access denied");
    }

    @Test
    void getDocumentById_cacheHit_returnsCachedDocumentWithoutDbQuery() {
        when(documentCacheService.get(docId)).thenReturn(Optional.of(userDoc));

        Optional<Document> doc = documentService.getDocumentById(docId, userDetails);

        assertThat(doc).isPresent();
        assertThat(doc.get().getFileName()).isEqualTo("test.pdf");
        verify(documentRepository, org.mockito.Mockito.never()).findById(any());
        verify(documentRepository, org.mockito.Mockito.never()).findByIdAndOwnerId(any(), any());
    }

    @Test
    void getDocumentStatus_returnsJobStatus() {
        when(documentRepository.findByIdAndOwnerId(docId, ownerId)).thenReturn(Optional.of(userDoc));
        com.docanalyser.redis.DocumentJobStatus status = new com.docanalyser.redis.DocumentJobStatus(
                "job-1", docId, DocumentStatus.PROCESSING, java.time.Instant.now(), java.time.Instant.now(), null
        );
        when(documentJobStatusService.getStatus(docId)).thenReturn(status);

        com.docanalyser.redis.DocumentJobStatus result = documentService.getDocumentStatus(docId, userDetails);

        assertThat(result).isNotNull();
        assertThat(result.getStatus()).isEqualTo(DocumentStatus.PROCESSING);
    }

    @Test
    void retryDocument_onFailedDocument_succeeds() {
        userDoc.setStatus(DocumentStatus.FAILED);
        when(documentRepository.findByIdAndOwnerId(docId, ownerId)).thenReturn(Optional.of(userDoc));
        when(ragServiceClient.ingestDocument(any())).thenReturn(java.util.Map.of("status", "success"));

        com.docanalyser.redis.DocumentJobStatus indexedStatus = new com.docanalyser.redis.DocumentJobStatus(
                "job-1", docId, DocumentStatus.INDEXED, java.time.Instant.now(), java.time.Instant.now(), null
        );
        when(documentJobStatusService.setStatus(eq(docId), eq(DocumentStatus.PROCESSING), any())).thenReturn(null);
        when(documentJobStatusService.setStatus(eq(docId), eq(DocumentStatus.INDEXED), any())).thenReturn(indexedStatus);

        com.docanalyser.redis.DocumentJobStatus result = documentService.retryDocument(docId, userDetails);

        assertThat(result.getStatus()).isEqualTo(DocumentStatus.INDEXED);
        verify(documentJobStatusService).setStatus(eq(docId), eq(DocumentStatus.PROCESSING), any());
        verify(documentJobStatusService).setStatus(eq(docId), eq(DocumentStatus.INDEXED), any());
        verify(documentCacheService, org.mockito.Mockito.atLeastOnce()).evict(docId);
    }

    @Test
    void retryDocument_onIndexedDocument_throwsIllegalStateException() {
        userDoc.setStatus(DocumentStatus.INDEXED);
        when(documentRepository.findByIdAndOwnerId(docId, ownerId)).thenReturn(Optional.of(userDoc));

        assertThatThrownBy(() -> documentService.retryDocument(docId, userDetails))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("Only FAILED documents can be retried");
    }
}
