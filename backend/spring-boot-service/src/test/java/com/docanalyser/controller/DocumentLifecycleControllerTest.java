package com.docanalyser.controller;

import com.docanalyser.auth.RagServiceException;
import com.docanalyser.client.RagServiceClient;
import com.docanalyser.dto.request.DocumentLifecycleRequest.DocumentEvent;
import com.docanalyser.dto.response.DocumentLifecycleResponse;
import com.docanalyser.security.SecurityConfig;
import com.docanalyser.security.jwt.AuthEntryPointJwt;
import com.docanalyser.security.jwt.JwtUtils;
import com.docanalyser.security.services.UserDetailsServiceImpl;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.security.test.context.support.WithMockUser;
import org.springframework.test.web.servlet.MockMvc;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(DocumentLifecycleController.class)
<<<<<<< HEAD
@AutoConfigureMockMvc(addFilters = false)
=======
@Import(SecurityConfig.class)
>>>>>>> 3458e31 (fix: authenticate document lifecycle controller tests)
class DocumentLifecycleControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private RagServiceClient ragServiceClient;

    // Required by SecurityConfig
    @MockBean
    private UserDetailsServiceImpl userDetailsService;

    @MockBean
    private AuthEntryPointJwt authEntryPointJwt;

    @MockBean
    private JwtUtils jwtUtils;

    @Test
    @WithMockUser(username = "test@example.com")
    void forwardsValidLifecycleRequest() throws Exception {
        when(ragServiceClient.processDocument(any())).thenReturn(
                new DocumentLifecycleResponse(true, "doc-123", DocumentEvent.DOCUMENT_ADDED, "PROCESSED", 2)
        );

        mockMvc.perform(post("/api/v1/documents")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"event":"DOCUMENT_ADDED","document_id":"doc-123","file_name":"research.txt","source_url":"C:/research.txt"}
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.document_id").value("doc-123"))
                .andExpect(jsonPath("$.status").value("PROCESSED"));
    }

    @Test
    @WithMockUser(username = "test@example.com")
    void rejectsMissingDocumentId() throws Exception {
        mockMvc.perform(post("/api/v1/documents")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"event":"DOCUMENT_DELETED"}
                                """))
                .andExpect(status().isBadRequest());
    }

    @Test
    @WithMockUser(username = "test@example.com")
    void propagatesPythonServiceFailure() throws Exception {
        when(ragServiceClient.processDocument(any())).thenThrow(
                new RagServiceException("RAG service returned HTTP 503", 503, null)
        );

        mockMvc.perform(post("/api/v1/documents")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"event":"DOCUMENT_DELETED","document_id":"doc-123"}
                                """))
                .andExpect(status().isServiceUnavailable())
                .andExpect(jsonPath("$.error").value("RAG service returned HTTP 503"));
    }
}