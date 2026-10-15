package com.docanalyser.redis;

import com.docanalyser.entity.Document;
import com.docanalyser.entity.DocumentStatus;
import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.io.Serializable;
import java.time.Instant;
import java.util.Objects;
import java.util.UUID;

/**
 * Representation of a document processing job stored in Redis.
 */
@JsonInclude(JsonInclude.Include.NON_NULL)
public class DocumentJobStatus implements Serializable {

    private String jobId;
    private UUID documentId;
    private DocumentStatus status;
    private Instant startedAt;
    private Instant updatedAt;

    @JsonProperty("error")
    private String errorMessage;

    @JsonProperty("retryCount")
    private Integer retryCount;

    public DocumentJobStatus() {
    }

    public DocumentJobStatus(String jobId, UUID documentId, DocumentStatus status,
                             Instant startedAt, Instant updatedAt, String errorMessage) {
        this(jobId, documentId, status, startedAt, updatedAt, errorMessage, 0);
    }

    public DocumentJobStatus(String jobId, UUID documentId, DocumentStatus status,
                             Instant startedAt, Instant updatedAt, String errorMessage, Integer retryCount) {
        this.jobId = jobId;
        this.documentId = documentId;
        this.status = status;
        this.startedAt = startedAt;
        this.updatedAt = updatedAt;
        this.errorMessage = errorMessage;
        this.retryCount = retryCount;
    }

    public static DocumentJobStatus fromDocument(Document doc) {
        if (doc == null) return null;
        return new DocumentJobStatus(
                doc.getId() != null ? doc.getId().toString() : UUID.randomUUID().toString(),
                doc.getId(),
                doc.getStatus(),
                doc.getCreatedAt(),
                doc.getUpdatedAt(),
                doc.getFailureReason(),
                doc.getRetryCount()
        );
    }

    public String getJobId() {
        return jobId;
    }

    public void setJobId(String jobId) {
        this.jobId = jobId;
    }

    public UUID getDocumentId() {
        return documentId;
    }

    public void setDocumentId(UUID documentId) {
        this.documentId = documentId;
    }

    public DocumentStatus getStatus() {
        return status;
    }

    public void setStatus(DocumentStatus status) {
        this.status = status;
    }

    public Instant getStartedAt() {
        return startedAt;
    }

    public void setStartedAt(Instant startedAt) {
        this.startedAt = startedAt;
    }

    public Instant getUpdatedAt() {
        return updatedAt;
    }

    public void setUpdatedAt(Instant updatedAt) {
        this.updatedAt = updatedAt;
    }

    public String getErrorMessage() {
        return errorMessage;
    }

    public void setErrorMessage(String errorMessage) {
        this.errorMessage = errorMessage;
    }

    public Integer getRetryCount() {
        return retryCount;
    }

    public void setRetryCount(Integer retryCount) {
        this.retryCount = retryCount;
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof DocumentJobStatus that)) return false;
        return Objects.equals(documentId, that.documentId) && status == that.status;
    }

    @Override
    public int hashCode() {
        return Objects.hash(documentId, status);
    }
}
