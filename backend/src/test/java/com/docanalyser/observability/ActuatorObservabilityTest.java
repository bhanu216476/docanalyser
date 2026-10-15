package com.docanalyser.observability;

import com.docanalyser.security.SecurityConfig;
import com.docanalyser.security.jwt.AuthEntryPointJwt;
import com.docanalyser.security.jwt.JwtUtils;
import com.docanalyser.security.services.UserDetailsServiceImpl;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
public class ActuatorObservabilityTest {

    @Autowired
    private MockMvc mockMvc;

    @Test
    public void testPrometheusEndpoint_isPermitted() throws Exception {
        mockMvc.perform(get("/actuator/prometheus"))
                .andExpect(status().isOk())
                .andExpect(header().exists("X-Request-Id"));
    }

    @Test
    public void testHealthEndpoint_isPermitted() throws Exception {
        mockMvc.perform(get("/actuator/health"))
                .andExpect(status().is(org.hamcrest.Matchers.in(java.util.List.of(200, 503))));
    }

    @Test
    public void testRequestIdHeader_isPreservedIfProvided() throws Exception {
        mockMvc.perform(get("/api/health").header("X-Request-Id", "custom-req-id-12345"))
                .andExpect(status().isOk())
                .andExpect(header().string("X-Request-Id", "custom-req-id-12345"));
    }
}
