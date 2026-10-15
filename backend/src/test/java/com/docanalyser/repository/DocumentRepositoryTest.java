package com.docanalyser.repository;

import com.docanalyser.entity.Document;
import com.docanalyser.entity.DocumentStatus;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase;

import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;

@DataJpaTest
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
class DocumentRepositoryTest {

    @Autowired
    private DocumentRepository documentRepository;

    @Test
    @DisplayName("Verify document metadata persistence, UUID generation, and retrieval")
    void testSaveAndRetrieveDocument() {
        Document doc = new Document(
                "architecture.txt",
                "txt",
                "text/plain",
                "/docs/architecture.txt",
                1024L,
                "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                DocumentStatus.PENDING
        );

        Document saved = documentRepository.save(doc);

        assertThat(saved.getId()).isNotNull();
        assertThat(saved.getId()).isInstanceOf(UUID.class);
        assertThat(saved.getFileName()).isEqualTo("architecture.txt");
        assertThat(saved.getFileType()).isEqualTo("txt");
        assertThat(saved.getMimeType()).isEqualTo("text/plain");
        assertThat(saved.getSource()).isEqualTo("/docs/architecture.txt");
        assertThat(saved.getFileSize()).isEqualTo(1024L);
        assertThat(saved.getContentHash()).isEqualTo("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855");
        assertThat(saved.getStatus()).isEqualTo(DocumentStatus.PENDING);
        assertThat(saved.getCreatedAt()).isNotNull();
        assertThat(saved.getUpdatedAt()).isNotNull();

        Optional<Document> retrieved = documentRepository.findById(saved.getId());
        assertThat(retrieved).isPresent();
        assertThat(retrieved.get().getFileName()).isEqualTo("architecture.txt");
        assertThat(retrieved.get().getFileSize()).isEqualTo(1024L);
    }

    @Test
    @DisplayName("Verify findByContentHash retrieves the expected document")
    void testFindByContentHash() {
        String hash = "112233445566778899aabbccddeeff00112233445566778899aabbccddeeff00";
        Document doc = new Document(
                "guide.md",
                "md",
                "text/markdown",
                "/docs/guide.md",
                2048L,
                hash,
                DocumentStatus.PENDING
        );
        documentRepository.save(doc);

        Optional<Document> found = documentRepository.findByContentHash(hash);
        assertThat(found).isPresent();
        assertThat(found.get().getFileName()).isEqualTo("guide.md");
    }

    @Test
    @DisplayName("Verify findByStatus filters documents by lifecycle status")
    void testFindByStatus() {
        Document pending = new Document(
                "pending.txt",
                "txt",
                "text/plain",
                "/docs/pending.txt",
                512L,
                "hash-pending-1",
                DocumentStatus.PENDING
        );
        Document processed = new Document(
                "processed.txt",
                "txt",
                "text/plain",
                "/docs/processed.txt",
                768L,
                "hash-processed-1",
                DocumentStatus.PROCESSED
        );

        documentRepository.save(pending);
        documentRepository.save(processed);

        List<Document> pendingDocs = documentRepository.findByStatus(DocumentStatus.PENDING);
        List<Document> processedDocs = documentRepository.findByStatus(DocumentStatus.PROCESSED);

        assertThat(pendingDocs).extracting(Document::getFileName).contains("pending.txt");
        assertThat(processedDocs).extracting(Document::getFileName).contains("processed.txt");
    }

    @Test
    @DisplayName("Verify status update transition")
    void testUpdateStatus() {
        Document doc = new Document(
                "workflow.md",
                "md",
                "text/markdown",
                "/docs/workflow.md",
                4096L,
                "hash-workflow-1",
                DocumentStatus.PENDING
        );
        Document saved = documentRepository.save(doc);

        saved.setStatus(DocumentStatus.PROCESSED);
        Document updated = documentRepository.save(saved);

        Optional<Document> retrieved = documentRepository.findById(updated.getId());
        assertThat(retrieved).isPresent();
        assertThat(retrieved.get().getStatus()).isEqualTo(DocumentStatus.PROCESSED);
    }
}
