package com.docanalyser.security;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.time.Instant;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;

@Component
@Order(Ordered.HIGHEST_PRECEDENCE + 1)
public class RateLimitingFilter extends OncePerRequestFilter {

    private static final Logger log = LoggerFactory.getLogger(RateLimitingFilter.class);

    private final ConcurrentHashMap<String, Window> windows = new ConcurrentHashMap<>();

    @Value("${app.rate-limit.requests-per-window:120}")
    private int requestsPerWindow;

    @Value("${app.rate-limit.window-ms:60000}")
    private long windowMs;

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain filterChain)
            throws ServletException, IOException {
        if (isExcluded(request)) {
            filterChain.doFilter(request, response);
            return;
        }

        String key = clientKey(request);
        long now = Instant.now().toEpochMilli();
        Window window = windows.computeIfAbsent(key, ignored -> new Window(now));

        if (!window.tryAcquire(now, windowMs, requestsPerWindow)) {
            long retryAfterSeconds = Math.max(1L, window.retryAfterSeconds(now, windowMs));
            response.setStatus(HttpStatus.TOO_MANY_REQUESTS.value());
            response.setHeader("Retry-After", Long.toString(retryAfterSeconds));
            response.setContentType(MediaType.APPLICATION_JSON_VALUE);
            response.getWriter().write("{\"error\":\"Too Many Requests\"}");
            log.warn("Rate limit exceeded for {} {} from {}", request.getMethod(), request.getRequestURI(), key);
            return;
        }

        filterChain.doFilter(request, response);
    }

    private boolean isExcluded(HttpServletRequest request) {
        String uri = request.getRequestURI();
        return uri.startsWith("/api/health") || uri.startsWith("/actuator/");
    }

    private String clientKey(HttpServletRequest request) {
        String forwardedFor = request.getHeader("X-Forwarded-For");
        if (forwardedFor != null && !forwardedFor.isBlank()) {
            return forwardedFor.split(",")[0].trim() + ":" + request.getRequestURI();
        }
        return request.getRemoteAddr() + ":" + request.getRequestURI();
    }

    private static final class Window {
        private volatile long windowStartMs;
        private final AtomicInteger requestCount = new AtomicInteger(0);

        private Window(long windowStartMs) {
            this.windowStartMs = windowStartMs;
        }

        private synchronized boolean tryAcquire(long now, long windowMs, int limit) {
            if (now - windowStartMs >= windowMs) {
                windowStartMs = now;
                requestCount.set(0);
            }

            if (requestCount.get() >= limit) {
                return false;
            }

            requestCount.incrementAndGet();
            return true;
        }

        private long retryAfterSeconds(long now, long windowMs) {
            long elapsed = now - windowStartMs;
            long remainingMs = Math.max(0L, windowMs - elapsed);
            return (remainingMs + 999L) / 1000L;
        }
    }
}