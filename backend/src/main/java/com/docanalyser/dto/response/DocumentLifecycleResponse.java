package com.docanalyser.dto.response;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.docanalyser.dto.request.DocumentLifecycleRequest.DocumentEvent;

public record DocumentLifecycleResponse(
        boolean success,
        @JsonProperty("document_id") String documentId,
        DocumentEvent event,
        String status,
        @JsonProperty("chunk_count") int chunkCount
) {
}