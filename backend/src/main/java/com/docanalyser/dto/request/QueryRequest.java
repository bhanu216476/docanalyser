package com.docanalyser.dto.request;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record QueryRequest(
    @NotBlank(message = "Query must not be blank")
    @Size(max = 1000, message = "Query must not exceed 1000 characters")
    String query
) {
}
