package com.docanalyser.client;

import com.docanalyser.auth.RagServiceException;
import com.docanalyser.dto.request.DocumentLifecycleRequest;
import com.docanalyser.dto.response.DocumentLifecycleResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpHeaders;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestClientResponseException;

@Service
public class RagServiceClient {
    private final RestClient restClient;
    private final String internalToken;

    public RagServiceClient(
            RestClient.Builder restClientBuilder,
            @Value("${rag.service.url}") String ragServiceUrl,
            @Value("${rag.service.internal-token:}") String internalToken
    ) {
        this.restClient = restClientBuilder.baseUrl(ragServiceUrl).build();
        this.internalToken = internalToken;
    }

    public DocumentLifecycleResponse processDocument(DocumentLifecycleRequest request) {
        try {
            return restClient.post()
                    .uri("/api/v1/documents")
                    .headers(headers -> addInternalToken(headers))
                    .body(request)
                    .retrieve()
                    .body(DocumentLifecycleResponse.class);
        } catch (RestClientResponseException exception) {
            throw new RagServiceException(
                    "RAG service returned HTTP " + exception.getStatusCode().value(),
                    exception.getStatusCode().value(),
                    exception
            );
        } catch (RestClientException exception) {
            throw new RagServiceException("RAG service is unavailable", 503, exception);
        }
    }

    private void addInternalToken(HttpHeaders headers) {
        if (internalToken != null && !internalToken.isBlank()) {
            headers.setBearerAuth(internalToken);
        }
    }
}