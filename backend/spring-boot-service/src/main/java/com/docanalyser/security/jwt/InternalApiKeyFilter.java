package com.docanalyser.security.jwt;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.authentication.WebAuthenticationDetailsSource;
import org.springframework.util.StringUtils;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.Collections;

public class InternalApiKeyFilter extends OncePerRequestFilter {

    private static final Logger log = LoggerFactory.getLogger(InternalApiKeyFilter.class);

    @Value("${app.internal.api-token:defaultN8nTokenForLocalDev}")
    private String internalApiToken;

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain filterChain)
            throws ServletException, IOException {
        
        String path = request.getRequestURI();
        // Only apply this filter to internal ingestion API
        if (path.startsWith("/api/internal/")) {
            String headerAuth = request.getHeader("X-Internal-Token");
            
            if (StringUtils.hasText(headerAuth) && headerAuth.equals(internalApiToken)) {
                // Create a system authentication context
                UsernamePasswordAuthenticationToken authentication =
                        new UsernamePasswordAuthenticationToken(
                                "system-internal",
                                null,
                                Collections.singletonList(new SimpleGrantedAuthority("ROLE_SYSTEM")));
                authentication.setDetails(new WebAuthenticationDetailsSource().buildDetails(request));
                SecurityContextHolder.getContext().setAuthentication(authentication);
                log.debug("Internal API authentication set for: {}", path);
            } else {
                log.warn("Internal API request to {} rejected: invalid or missing X-Internal-Token", path);
            }
        }
        
        filterChain.doFilter(request, response);
    }
}
