package com.docanalyser.redis;

import java.util.UUID;

/**
 * Consistent Redis key naming conventions.
 *
 * Keys format:
 * - document:status:{documentId}
 * - cache:document:{documentId}
 * - session:{sessionId}
 */
public final class RedisKeys {

    private RedisKeys() {}

    public static final String DOCUMENT_STATUS_PREFIX = "document:status:";
    public static final String DOCUMENT_CACHE_PREFIX = "cache:document:";
    public static final String SESSION_PREFIX = "session:";

    public static String documentStatusKey(UUID documentId) {
        if (documentId == null) {
            throw new IllegalArgumentException("documentId cannot be null");
        }
        return DOCUMENT_STATUS_PREFIX + documentId;
    }

    public static String documentCacheKey(UUID documentId) {
        if (documentId == null) {
            throw new IllegalArgumentException("documentId cannot be null");
        }
        return DOCUMENT_CACHE_PREFIX + documentId;
    }

    public static String sessionKey(UUID sessionId) {
        if (sessionId == null) {
            throw new IllegalArgumentException("sessionId cannot be null");
        }
        return SESSION_PREFIX + sessionId;
    }
}
