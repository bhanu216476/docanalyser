package com.docanalyser.redis;

import com.docanalyser.entity.Document;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Service;

import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.TimeUnit;

/**
 * Service providing caching for Document entities with Redis and graceful fallback.
 *
 * Invalidation Strategy:
 * - Evicted on Document update
 * - Evicted on Document delete
 * - Evicted when Document processing status transitions
 */
@Service
public class DocumentCacheService {

    private static final Logger log = LoggerFactory.getLogger(DocumentCacheService.class);

    private final RedisTemplate<String, Object> redisTemplate;

    @Value("${app.redis.cache-document-ttl-seconds:300}")
    private long cacheDocumentTtlSeconds;

    public DocumentCacheService(RedisTemplate<String, Object> redisTemplate) {
        this.redisTemplate = redisTemplate;
    }

    /**
     * Retrieves cached Document by ID. Returns empty if cache miss or Redis is unavailable.
     */
    public Optional<Document> get(UUID documentId) {
        if (documentId == null) return Optional.empty();

        String key = RedisKeys.documentCacheKey(documentId);
        try {
            Object obj = redisTemplate.opsForValue().get(key);
            if (obj instanceof Document document) {
                log.debug("Cache hit for document {}", documentId);
                return Optional.of(document);
            }
        } catch (Exception e) {
            log.warn("Redis unavailable during cache read for document {}: {}", documentId, e.getMessage());
        }

        return Optional.empty();
    }

    /**
     * Stores document in cache with configurable TTL.
     */
    public void put(Document document) {
        if (document == null || document.getId() == null) return;

        String key = RedisKeys.documentCacheKey(document.getId());
        try {
            redisTemplate.opsForValue().set(key, document, cacheDocumentTtlSeconds, TimeUnit.SECONDS);
            log.debug("Cached document {} with TTL {}s", document.getId(), cacheDocumentTtlSeconds);
        } catch (Exception e) {
            log.warn("Redis unavailable during cache put for document {}: {}", document.getId(), e.getMessage());
        }
    }

    /**
     * Evicts document from cache.
     */
    public void evict(UUID documentId) {
        if (documentId == null) return;

        String key = RedisKeys.documentCacheKey(documentId);
        try {
            redisTemplate.delete(key);
            log.debug("Evicted document {} from cache", documentId);
        } catch (Exception e) {
            log.warn("Redis unavailable during cache evict for document {}: {}", documentId, e.getMessage());
        }
    }
}
