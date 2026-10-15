package com.docanalyser.dto.request;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

import java.util.Map;

public record DocumentLifecycleRequest(
        @NotNull(message = "Event must not be null") DocumentEvent event,
        @NotBlank(message = "Document ID must not be blank") @JsonProperty("document_id") String documentId,
        @JsonProperty("file_name") String fileName,
        @JsonProperty("source_url") String sourceUrl,
        @JsonProperty("content_type") String contentType,
        Map<String, Object> metadata,
        String version,
        @JsonProperty("updated_at") String updatedAt
) {
    public enum DocumentEvent {
        DOCUMENT_ADDED,
        DOCUMENT_UPDATED,
        DOCUMENT_DELETED
    }
}