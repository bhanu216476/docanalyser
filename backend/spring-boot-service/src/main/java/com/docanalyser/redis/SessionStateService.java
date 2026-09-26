package com.docanalyser.redis;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.TimeUnit;

/**
 * Service managing temporary session state in Redis.
 * PostgreSQL remains the source of truth for persistent chat sessions and messages.
 */
@Service
public class SessionStateService {

    private static final Logger log = LoggerFactory.getLogger(SessionStateService.class);

    private final RedisTemplate<String, Object> redisTemplate;

    @Value("${app.redis.session-state-ttl-seconds:1800}")
    private long sessionStateTtlSeconds;

    public SessionStateService(RedisTemplate<String, Object> redisTemplate) {
        this.redisTemplate = redisTemplate;
    }

    /**
     * Updates or records active session state with refreshed TTL.
     */
    public void touchSession(UUID sessionId, UUID userId) {
        if (sessionId == null || userId == null) return;

        SessionState state = new SessionState(sessionId, userId, Instant.now(), "ACTIVE");
        String key = RedisKeys.sessionKey(sessionId);
        try {
            redisTemplate.opsForValue().set(key, state, sessionStateTtlSeconds, TimeUnit.SECONDS);
            log.debug("Refreshed session state for session {} with TTL {}s", sessionId, sessionStateTtlSeconds);
        } catch (Exception e) {
            log.warn("Redis unavailable during session state touch for session {}: {}", sessionId, e.getMessage());
        }
    }

    /**
     * Retrieves session state from Redis.
     */
    public Optional<SessionState> getSessionState(UUID sessionId) {
        if (sessionId == null) return Optional.empty();

        String key = RedisKeys.sessionKey(sessionId);
        try {
            Object obj = redisTemplate.opsForValue().get(key);
            if (obj instanceof SessionState state) {
                return Optional.of(state);
            }
        } catch (Exception e) {
            log.warn("Redis unavailable during session state get for session {}: {}", sessionId, e.getMessage());
        }
        return Optional.empty();
    }

    /**
     * Removes session state from Redis upon session termination or deletion.
     */
    public void deleteSessionState(UUID sessionId) {
        if (sessionId == null) return;

        String key = RedisKeys.sessionKey(sessionId);
        try {
            redisTemplate.delete(key);
            log.debug("Deleted session state for session {}", sessionId);
        } catch (Exception e) {
            log.warn("Redis unavailable during session state delete for session {}: {}", sessionId, e.getMessage());
        }
    }
}
