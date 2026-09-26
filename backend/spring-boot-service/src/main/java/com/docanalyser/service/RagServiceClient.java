package com.docanalyser.service;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.web.client.RestTemplateBuilder;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Service;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.server.ResponseStatusException;

import com.docanalyser.dto.request.IngestionRequest;

import java.time.Duration;
import java.util.Map;

@Service
public class RagServiceClient {

    @Value("${app.rag-service.url:http://localhost:8000}")
    private String ragServiceUrl;

    @Value("${app.rag-service.connect-timeout-ms:5000}")
    private int connectTimeoutMs;

    @Value("${app.rag-service.read-timeout-ms:60000}")
    private int readTimeoutMs;

    private final RestTemplateBuilder restTemplateBuilder;

    public RagServiceClient(RestTemplateBuilder restTemplateBuilder) {
        this.restTemplateBuilder = restTemplateBuilder;
    }

    private RestTemplate buildRestTemplate() {
        return restTemplateBuilder
                .setConnectTimeout(Duration.ofMillis(connectTimeoutMs))
                .setReadTimeout(Duration.ofMillis(readTimeoutMs))
                .build();
    }

    /**
     * Sends a query to the Python RAG service. Returns the full response body map.
     * Python endpoint: POST /api/v1/rag/query
     */
    public Map<String, Object> queryRagService(String query) {
        String url = ragServiceUrl + "/api/v1/rag/query";

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);

        Map<String, Object> requestBody = Map.of("query", query);
        HttpEntity<Map<String, Object>> request = new HttpEntity<>(requestBody, headers);

        try {
            ResponseEntity<Map> response = buildRestTemplate().postForEntity(url, request, Map.class);
            if (response.getStatusCode().is2xxSuccessful() && response.getBody() != null) {
                return response.getBody();
            } else {
                throw new ResponseStatusException(HttpStatus.BAD_GATEWAY,
                        "RAG service returned unexpected status: " + response.getStatusCode());
            }
        } catch (ResourceAccessException e) {
            throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE,
                    "RAG service is unreachable", e);
        } catch (RestClientException e) {
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY,
                    "Failed to communicate with RAG service: " + e.getMessage(), e);
        }
    }

    /**
     * Sends a document ingestion request to the Python RAG service.
     * Python endpoint: POST /api/v1/rag/ingest (multipart form: file_path or file)
     * We send as JSON with the file URL for URL-based ingestion.
     */
    public Map<String, Object> ingestDocument(IngestionRequest ingestionRequest) {
        String url = ragServiceUrl + "/api/v1/rag/ingest";

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_FORM_URLENCODED);

        // Python service accepts file_path as form field
        String formBody = "file_path=" + java.net.URLEncoder.encode(
                ingestionRequest.getFileUrl() != null ? ingestionRequest.getFileUrl() : "",
                java.nio.charset.StandardCharsets.UTF_8);

        HttpEntity<String> request = new HttpEntity<>(formBody, headers);

        try {
            ResponseEntity<Map> response = buildRestTemplate().postForEntity(url, request, Map.class);
            if (response.getStatusCode().is2xxSuccessful() && response.getBody() != null) {
                return response.getBody();
            } else {
                throw new ResponseStatusException(HttpStatus.BAD_GATEWAY,
                        "RAG ingestion service returned unexpected status: " + response.getStatusCode());
            }
        } catch (ResourceAccessException e) {
            throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE,
                    "RAG service is unreachable", e);
        } catch (RestClientException e) {
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY,
                    "Failed to communicate with RAG ingestion service: " + e.getMessage(), e);
        }
    }
}

