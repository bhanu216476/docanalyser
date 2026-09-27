package com.docanalyser.redis;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.redis.RedisConnectionFailureException;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.data.redis.core.ValueOperations;

import java.time.Instant;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.TimeUnit;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class SessionStateServiceTest {

    @Mock
    private RedisTemplate<String, Object> redisTemplate;

    @Mock
    private ValueOperations<String, Object> valueOperations;

    @InjectMocks
    private SessionStateService sessionStateService;

    private UUID sessionId;
    private UUID userId;
    private String sessionKey;

    @BeforeEach
    void setUp() {
        sessionId = UUID.randomUUID();
        userId = UUID.randomUUID();
        sessionKey = RedisKeys.sessionKey(sessionId);
    }

    @Test
    @DisplayName("touchSession writes SessionState to Redis with TTL")
    void touchSession_writesToRedis() {
        when(redisTemplate.opsForValue()).thenReturn(valueOperations);

        sessionStateService.touchSession(sessionId, userId);

        verify(valueOperations).set(eq(sessionKey), any(SessionState.class), anyLong(), eq(TimeUnit.SECONDS));
    }

    @Test
    @DisplayName("touchSession handles Redis failure gracefully")
    void touchSession_redisFailure_doesNotThrow() {
        when(redisTemplate.opsForValue()).thenReturn(valueOperations);
        org.mockito.Mockito.doThrow(new RedisConnectionFailureException("Connection refused"))
                .when(valueOperations).set(eq(sessionKey), any(SessionState.class), anyLong(), eq(TimeUnit.SECONDS));

        assertThatCode(() -> sessionStateService.touchSession(sessionId, userId)).doesNotThrowAnyException();
    }

    @Test
    @DisplayName("getSessionState returns SessionState when present")
    void getSessionState_returnsState() {
        when(redisTemplate.opsForValue()).thenReturn(valueOperations);
        SessionState state = new SessionState(sessionId, userId, Instant.now(), "ACTIVE");
        when(valueOperations.get(sessionKey)).thenReturn(state);

        Optional<SessionState> result = sessionStateService.getSessionState(sessionId);

        assertThat(result).isPresent();
        assertThat(result.get().getSessionId()).isEqualTo(sessionId);
        assertThat(result.get().getStatus()).isEqualTo("ACTIVE");
    }

    @Test
    @DisplayName("deleteSessionState deletes key from Redis")
    void deleteSessionState_deletesKey() {
        sessionStateService.deleteSessionState(sessionId);

        verify(redisTemplate).delete(sessionKey);
    }
}
