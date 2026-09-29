package com.docanalyser.observability;

import io.micrometer.tracing.Span;
import io.micrometer.tracing.Tracer;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.UUID;

/**
 * Filter that establishes MDC context (requestId, traceId, spanId) and logs
 * structured HTTP request completion and durations.
 */
@Component
@Order(Ordered.HIGHEST_PRECEDENCE)
public class RequestLoggingFilter extends OncePerRequestFilter {

    private static final Logger log = LoggerFactory.getLogger(RequestLoggingFilter.class);

    private final Tracer tracer;

    public RequestLoggingFilter(@Autowired(required = false) Tracer tracer) {
        this.tracer = tracer;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain filterChain)
            throws ServletException, IOException {

        long startTime = System.currentTimeMillis();

        String requestId = request.getHeader("X-Request-Id");
        if (requestId == null || requestId.isBlank()) {
            requestId = UUID.randomUUID().toString();
        }
        response.setHeader("X-Request-Id", requestId);

        MDC.put("requestId", requestId);
        MDC.put("request_id", requestId);
        MDC.put("operation_name", request.getMethod() + " " + request.getRequestURI());

        if (tracer != null) {
            Span currentSpan = tracer.currentSpan();
            if (currentSpan != null && currentSpan.context() != null) {
                String traceId = currentSpan.context().traceId();
                String spanId = currentSpan.context().spanId();
                if (traceId != null) {
                    MDC.put("traceId", traceId);
                    MDC.put("trace_id", traceId);
                }
                if (spanId != null) {
                    MDC.put("spanId", spanId);
                    MDC.put("span_id", spanId);
                }
            }
        }

        try {
            filterChain.doFilter(request, response);
        } catch (Exception ex) {
            MDC.put("error_type", ex.getClass().getSimpleName());
            throw ex;
        } finally {
            long durationMs = System.currentTimeMillis() - startTime;
            MDC.put("duration_ms", String.valueOf(durationMs));

            // Avoid logging excessive noise for actuator health polls if needed, but log all normal endpoints
            String uri = request.getRequestURI();
            if (!uri.startsWith("/actuator/health")) {
                log.info("HTTP {} {} completed with status {} in {}ms",
                        request.getMethod(), uri, response.getStatus(), durationMs);
            }

            MDC.remove("requestId");
            MDC.remove("request_id");
            MDC.remove("traceId");
            MDC.remove("trace_id");
            MDC.remove("spanId");
            MDC.remove("span_id");
            MDC.remove("operation_name");
            MDC.remove("duration_ms");
            MDC.remove("error_type");
        }
    }
}
