package com.docanalyser.redis;

import java.io.Serializable;
import java.time.Instant;
import java.util.Objects;
import java.util.UUID;

/**
 * Short-lived session state stored in Redis.
 */
public class SessionState implements Serializable {

    private UUID sessionId;
    private UUID userId;
    private Instant lastActivityAt;
    private String status;

    public SessionState() {
    }

    public SessionState(UUID sessionId, UUID userId, Instant lastActivityAt, String status) {
        this.sessionId = sessionId;
        this.userId = userId;
        this.lastActivityAt = lastActivityAt;
        this.status = status;
    }

    public UUID getSessionId() {
        return sessionId;
    }

    public void setSessionId(UUID sessionId) {
        this.sessionId = sessionId;
    }

    public UUID getUserId() {
        return userId;
    }

    public void setUserId(UUID userId) {
        this.userId = userId;
    }

    public Instant getLastActivityAt() {
        return lastActivityAt;
    }

    public void setLastActivityAt(Instant lastActivityAt) {
        this.lastActivityAt = lastActivityAt;
    }

    public String getStatus() {
        return status;
    }

    public void setStatus(String status) {
        this.status = status;
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof SessionState that)) return false;
        return Objects.equals(sessionId, that.sessionId) && Objects.equals(userId, that.userId);
    }

    @Override
    public int hashCode() {
        return Objects.hash(sessionId, userId);
    }
}
