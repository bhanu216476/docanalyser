package com.docanalyser.dto.response;

import java.util.List;

public record QueryResponse(
    String answer,
    List<CitationResponse> citations
) {
}
