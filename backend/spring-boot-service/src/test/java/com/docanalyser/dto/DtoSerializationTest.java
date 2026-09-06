package com.docanalyser.dto;

import com.docanalyser.dto.request.QueryRequest;
import com.docanalyser.dto.response.CitationResponse;
import com.docanalyser.dto.response.QueryResponse;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;

class DtoSerializationTest {

    private final ObjectMapper objectMapper = new ObjectMapper();

    @Test
    void testQueryRequestSerialization() throws Exception {
        QueryRequest request = new QueryRequest("What is the leave policy?");
        String json = objectMapper.writeValueAsString(request);
        
        assertEquals("{\"query\":\"What is the leave policy?\"}", json);
        
        QueryRequest deserialized = objectMapper.readValue(json, QueryRequest.class);
        assertEquals(request.query(), deserialized.query());
    }

    @Test
    void testQueryResponseSerialization() throws Exception {
        CitationResponse citation = new CitationResponse("employee-handbook.pdf", 12);
        QueryResponse response = new QueryResponse("Employees are entitled to...", List.of(citation));
        
        String json = objectMapper.writeValueAsString(response);
        
        QueryResponse deserialized = objectMapper.readValue(json, QueryResponse.class);
        assertEquals(response.answer(), deserialized.answer());
        assertEquals(1, deserialized.citations().size());
        
        CitationResponse deserializedCitation = deserialized.citations().get(0);
        assertEquals(citation.document(), deserializedCitation.document());
        assertEquals(citation.page(), deserializedCitation.page());
    }
}
