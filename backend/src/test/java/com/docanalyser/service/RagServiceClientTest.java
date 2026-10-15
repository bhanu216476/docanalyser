package com.docanalyser.service;

import com.docanalyser.dto.request.IngestionRequest;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.Spy;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.boot.web.client.RestTemplateBuilder;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.server.ResponseStatusException;

import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class RagServiceClientTest {

    @Mock
    private RestTemplateBuilder restTemplateBuilder;

    @Mock
    private RestTemplate restTemplate;

    private RagServiceClient ragServiceClient;

    @BeforeEach
    void setUp() {
        when(restTemplateBuilder.setConnectTimeout(any())).thenReturn(restTemplateBuilder);
        when(restTemplateBuilder.setReadTimeout(any())).thenReturn(restTemplateBuilder);
        when(restTemplateBuilder.build()).thenReturn(restTemplate);

        ragServiceClient = new RagServiceClient(restTemplateBuilder);
        ReflectionTestUtils.setField(ragServiceClient, "ragServiceUrl", "http://localhost:8000");
        ReflectionTestUtils.setField(ragServiceClient, "connectTimeoutMs", 5000);
        ReflectionTestUtils.setField(ragServiceClient, "readTimeoutMs", 60000);
    }

    @Test
    void queryRagService_successfulResponse_returnsResponseMap() {
        Map<String, Object> body = Map.of("answer", "Test answer", "query", "Test query");
        ResponseEntity<Map> responseEntity = new ResponseEntity<>(body, HttpStatus.OK);
        when(restTemplate.postForEntity(anyString(), any(), eq(Map.class))).thenReturn(responseEntity);

        Map<String, Object> result = ragServiceClient.queryRagService("Test query");

        assertThat(result.get("answer")).isEqualTo("Test answer");
    }

    @Test
    void queryRagService_serviceUnavailable_throws503() {
        when(restTemplate.postForEntity(anyString(), any(), eq(Map.class)))
                .thenThrow(new ResourceAccessException("Connection refused"));

        assertThatThrownBy(() -> ragServiceClient.queryRagService("Test query"))
                .isInstanceOf(ResponseStatusException.class)
                .extracting(e -> ((ResponseStatusException) e).getStatusCode())
                .isEqualTo(HttpStatus.SERVICE_UNAVAILABLE);
    }

    @Test
    void queryRagService_badGateway_throws502() {
        ResponseEntity<Map> responseEntity = new ResponseEntity<>(null, HttpStatus.INTERNAL_SERVER_ERROR);
        when(restTemplate.postForEntity(anyString(), any(), eq(Map.class))).thenReturn(responseEntity);

        assertThatThrownBy(() -> ragServiceClient.queryRagService("Test query"))
                .isInstanceOf(ResponseStatusException.class)
                .extracting(e -> ((ResponseStatusException) e).getStatusCode())
                .isEqualTo(HttpStatus.BAD_GATEWAY);
    }

    @Test
    void ingestDocument_successfulResponse_returnsResponseMap() {
        IngestionRequest ingestionRequest = new IngestionRequest();
        ingestionRequest.setDocumentId("doc123");
        ingestionRequest.setFileName("test.pdf");
        ingestionRequest.setSource("google-drive");
        ingestionRequest.setFileUrl("/path/to/file.pdf");

        Map<String, Object> body = Map.of("document_id", "doc123", "chunk_count", 5);
        ResponseEntity<Map> responseEntity = new ResponseEntity<>(body, HttpStatus.CREATED);
        when(restTemplate.postForEntity(anyString(), any(), eq(Map.class))).thenReturn(responseEntity);

        Map<String, Object> result = ragServiceClient.ingestDocument(ingestionRequest);

        assertThat(result.get("document_id")).isEqualTo("doc123");
    }

    @Test
    void ingestDocument_serviceUnavailable_throws503() {
        IngestionRequest ingestionRequest = new IngestionRequest();
        ingestionRequest.setFileUrl("/some/path.pdf");

        when(restTemplate.postForEntity(anyString(), any(), eq(Map.class)))
                .thenThrow(new ResourceAccessException("Connection refused"));

        assertThatThrownBy(() -> ragServiceClient.ingestDocument(ingestionRequest))
                .isInstanceOf(ResponseStatusException.class)
                .extracting(e -> ((ResponseStatusException) e).getStatusCode())
                .isEqualTo(HttpStatus.SERVICE_UNAVAILABLE);
    }
}
