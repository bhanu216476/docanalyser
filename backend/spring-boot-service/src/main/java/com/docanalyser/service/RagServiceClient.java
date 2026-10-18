package com.docanalyser.service;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.web.client.RestTemplateBuilder;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Service;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.server.ResponseStatusException;

import com.docanalyser.dto.request.IngestionRequest;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.Map;
import java.util.UUID;

@Service("documentRagServiceClient")
public class RagServiceClient {

    private static final Logger log = LoggerFactory.getLogger(RagServiceClient.class);

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
        return queryRagService(query, null);
    }

    /**
     * Sends a query to the Python RAG service with document or metadata filters.
     * Python endpoint: POST /api/v1/rag/query
     */
    @SuppressWarnings("unchecked")
    public Map<String, Object> queryRagService(String query, Map<String, Object> filters) {
        String url = ragServiceUrl + "/api/v1/rag/query";

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);

        String correlationId = org.slf4j.MDC.get("correlationId");
        if (correlationId == null || correlationId.isBlank()) {
            correlationId = UUID.randomUUID().toString();
        }
        headers.set("X-Correlation-ID", correlationId);
        headers.set("X-Request-ID", correlationId);

        java.util.Map<String, Object> requestBody = new java.util.HashMap<>();
        requestBody.put("query", query);
        if (filters != null && !filters.isEmpty()) {
            requestBody.put("filters", filters);
        }

        HttpEntity<Map<String, Object>> request = new HttpEntity<>(requestBody, headers);

        try {
            @SuppressWarnings("rawtypes")
            ResponseEntity<Map> response = buildRestTemplate().postForEntity(url, request, Map.class);
            if (response.getStatusCode().is2xxSuccessful() && response.getBody() != null) {
                return (Map<String, Object>) response.getBody();
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
     * Ingests a document into the Python RAG service.
     * Python endpoint: POST /api/v1/rag/ingest (multipart/form-data: file)
     *
     * <p>Downloads the document from the provided fileUrl and sends it as a
     * multipart upload. The Python service only accepts a local file path or
     * a file upload — it does not accept remote URLs directly.
     */
    @SuppressWarnings("unchecked")
    public Map<String, Object> ingestDocument(IngestionRequest ingestionRequest) {
        String fileUrl = ingestionRequest.getFileUrl();
        String fileName = ingestionRequest.getFileName() != null ? ingestionRequest.getFileName() : "document.bin";

        // Step 1: Download the file bytes from the remote URL or treat as raw text
        byte[] fileBytes;
        if (fileUrl != null && (fileUrl.startsWith("http://") || fileUrl.startsWith("https://"))) {
            try {
                log.info("Downloading document for ingestion from: {}", fileUrl);
                HttpClient httpClient = HttpClient.newBuilder()
                        .connectTimeout(Duration.ofMillis(connectTimeoutMs))
                        .build();
                HttpRequest downloadRequest = HttpRequest.newBuilder()
                        .uri(URI.create(fileUrl))
                        .timeout(Duration.ofMillis(readTimeoutMs))
                        .GET()
                        .build();
                HttpResponse<byte[]> downloadResponse = httpClient.send(downloadRequest, HttpResponse.BodyHandlers.ofByteArray());
                if (downloadResponse.statusCode() < 200 || downloadResponse.statusCode() >= 300) {
                    throw new ResponseStatusException(HttpStatus.BAD_GATEWAY,
                            "Failed to download document from URL: HTTP " + downloadResponse.statusCode());
                }
                fileBytes = downloadResponse.body();
                log.info("Downloaded {} bytes for document: {}", fileBytes.length, fileName);
            } catch (IOException | InterruptedException e) {
                Thread.currentThread().interrupt();
                throw new ResponseStatusException(HttpStatus.BAD_GATEWAY,
                        "Failed to download document from URL: " + e.getMessage(), e);
            }
        } else if (fileUrl != null && fileUrl.startsWith("data:")) {
            log.info("Processing document as base64 data URI");
            int commaIndex = fileUrl.indexOf(',');
            if (commaIndex != -1) {
                String base64Data = fileUrl.substring(commaIndex + 1);
                fileBytes = java.util.Base64.getDecoder().decode(base64Data);
            } else {
                fileBytes = new byte[0];
            }
        } else {
            // Treat fileUrl as raw text content directly
            log.info("Processing document as raw text string");
            fileBytes = fileUrl != null ? fileUrl.getBytes(java.nio.charset.StandardCharsets.UTF_8) : new byte[0];
        }

        // Step 2: Send as multipart/form-data to the Python RAG service
        String ingestUrl = ragServiceUrl + "/api/v1/rag/ingest";

        ByteArrayResource fileResource = new ByteArrayResource(fileBytes) {
            @Override
            public String getFilename() {
                return fileName;
            }
        };

        MultiValueMap<String, Object> body = new LinkedMultiValueMap<>();
        body.add("file", fileResource);

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.MULTIPART_FORM_DATA);

        HttpEntity<MultiValueMap<String, Object>> requestEntity = new HttpEntity<>(body, headers);

        try {
            @SuppressWarnings("rawtypes")
            ResponseEntity<Map> response = buildRestTemplate().postForEntity(ingestUrl, requestEntity, Map.class);
            if (response.getStatusCode().is2xxSuccessful() && response.getBody() != null) {
                return (Map<String, Object>) response.getBody();
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

    /**
     * Deletes a document's embeddings and lexical index from the Python RAG service.
     * Python endpoint: POST /api/v1/documents (event: DOCUMENT_DELETED)
     */
    @SuppressWarnings("unchecked")
    public Map<String, Object> deleteDocument(UUID documentId) {
        if (documentId == null) {
            return Map.of("success", true);
        }
        String url = ragServiceUrl + "/api/v1/documents";

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);

        String correlationId = org.slf4j.MDC.get("correlationId");
        if (correlationId == null || correlationId.isBlank()) {
            correlationId = UUID.randomUUID().toString();
        }
        headers.set("X-Correlation-ID", correlationId);
        headers.set("X-Request-ID", correlationId);

        Map<String, Object> requestBody = Map.of(
                "event", "DOCUMENT_DELETED",
                "document_id", documentId.toString()
        );
        HttpEntity<Map<String, Object>> request = new HttpEntity<>(requestBody, headers);

        try {
            @SuppressWarnings("rawtypes")
            ResponseEntity<Map> response = buildRestTemplate().postForEntity(url, request, Map.class);
            if (response.getStatusCode().is2xxSuccessful() && response.getBody() != null) {
                log.info("Successfully cleaned up RAG vectors for document {}", documentId);
                return (Map<String, Object>) response.getBody();
            } else {
                log.warn("RAG deletion returned status: {}", response.getStatusCode());
                return Map.of("success", false, "status", response.getStatusCode().toString());
            }
        } catch (Exception e) {
            log.error("Failed to clean up RAG vectors for document {}: {}", documentId, e.getMessage());
            return Map.of("success", false, "error", e.getMessage() != null ? e.getMessage() : "Deletion failed");
        }
    }
}

