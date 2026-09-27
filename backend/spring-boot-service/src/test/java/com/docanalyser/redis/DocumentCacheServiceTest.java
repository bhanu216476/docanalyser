package com.docanalyser.redis;

import com.docanalyser.entity.Document;
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

import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.TimeUnit;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class DocumentCacheServiceTest {

    @Mock
    private RedisTemplate<String, Object> redisTemplate;

    @Mock
    private ValueOperations<String, Object> valueOperations;

    @InjectMocks
    private DocumentCacheService cacheService;

    private UUID docId;
    private String cacheKey;
    private Document document;

    @BeforeEach
    void setUp() {
        docId = UUID.randomUUID();
        cacheKey = RedisKeys.documentCacheKey(docId);
        document = new Document("report.pdf", "pdf", "application/pdf", "source", 2048L, "hash123");
        document.setId(docId);
    }

    @Test
    @DisplayName("get returns cached Document when present")
    void get_cacheHit_returnsDocument() {
        when(redisTemplate.opsForValue()).thenReturn(valueOperations);
        when(valueOperations.get(cacheKey)).thenReturn(document);

        Optional<Document> result = cacheService.get(docId);

        assertThat(result).isPresent();
        assertThat(result.get().getFileName()).isEqualTo("report.pdf");
    }

    @Test
    @DisplayName("get returns empty Optional on cache miss")
    void get_cacheMiss_returnsEmpty() {
        when(redisTemplate.opsForValue()).thenReturn(valueOperations);
        when(valueOperations.get(cacheKey)).thenReturn(null);

        Optional<Document> result = cacheService.get(docId);

        assertThat(result).isEmpty();
    }

    @Test
    @DisplayName("get gracefully returns empty Optional when Redis is down without throwing")
    void get_redisFailure_returnsEmptyGracefully() {
        when(redisTemplate.opsForValue()).thenReturn(valueOperations);
        when(valueOperations.get(cacheKey)).thenThrow(new RedisConnectionFailureException("Connection refused"));

        Optional<Document> result = cacheService.get(docId);

        assertThat(result).isEmpty();
    }

    @Test
    @DisplayName("put stores document in Redis with configured TTL")
    void put_storesInRedis() {
        when(redisTemplate.opsForValue()).thenReturn(valueOperations);

        cacheService.put(document);

        verify(valueOperations).set(eq(cacheKey), eq(document), anyLong(), eq(TimeUnit.SECONDS));
    }

    @Test
    @DisplayName("put handles Redis failure gracefully without throwing")
    void put_redisFailure_doesNotThrow() {
        when(redisTemplate.opsForValue()).thenReturn(valueOperations);
        org.mockito.Mockito.doThrow(new RedisConnectionFailureException("Connection refused"))
                .when(valueOperations).set(eq(cacheKey), eq(document), anyLong(), eq(TimeUnit.SECONDS));

        assertThatCode(() -> cacheService.put(document)).doesNotThrowAnyException();
    }

    @Test
    @DisplayName("evict deletes document cache key")
    void evict_deletesKey() {
        cacheService.evict(docId);

        verify(redisTemplate).delete(cacheKey);
    }

    @Test
    @DisplayName("evict handles Redis failure gracefully without throwing")
    void evict_redisFailure_doesNotThrow() {
        when(redisTemplate.delete(cacheKey)).thenThrow(new RedisConnectionFailureException("Connection refused"));

        assertThatCode(() -> cacheService.evict(docId)).doesNotThrowAnyException();
    }
}
