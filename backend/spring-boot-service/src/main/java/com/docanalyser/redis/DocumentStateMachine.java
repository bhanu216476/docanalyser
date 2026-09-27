package com.docanalyser.redis;

import com.docanalyser.entity.DocumentStatus;

/**
 * State machine enforcing valid document processing lifecycle transitions.
 *
 * Allowed paths:
 * UPLOADED -> PROCESSING -> INDEXED
 * PROCESSING -> FAILED
 * FAILED -> PROCESSING (Retry)
 *
 * PENDING is supported for backward compatibility (PENDING -> UPLOADED / PROCESSING).
 * READY and PROCESSED are recognized terminal states (synonymous with INDEXED).
 */
public final class DocumentStateMachine {

    private DocumentStateMachine() {}

    /**
     * Determines whether transitioning from current status to target status is permitted.
     *
     * @param current current DocumentStatus (can be null for initial creation)
     * @param next target DocumentStatus (cannot be null)
     * @return true if transition is valid
     */
    public static boolean isValidTransition(DocumentStatus current, DocumentStatus next) {
        if (next == null) {
            return false;
        }

        // Initial creation
        if (current == null) {
            return next == DocumentStatus.UPLOADED || next == DocumentStatus.PENDING;
        }

        // Idempotent update
        if (current == next) {
            return true;
        }

        return switch (current) {
            case PENDING -> next == DocumentStatus.UPLOADED || next == DocumentStatus.PROCESSING;
            case UPLOADED -> next == DocumentStatus.PROCESSING;
            case PROCESSING -> next == DocumentStatus.INDEXED
                    || next == DocumentStatus.READY
                    || next == DocumentStatus.PROCESSED
                    || next == DocumentStatus.FAILED;
            case FAILED -> next == DocumentStatus.PROCESSING; // Only allowed transition from FAILED is retry
            case INDEXED, READY, PROCESSED -> false; // Terminal states cannot transition
        };
    }

    /**
     * Validates transition and throws {@link IllegalStateException} if not permitted.
     */
    public static void validateTransition(DocumentStatus current, DocumentStatus next) {
        if (!isValidTransition(current, next)) {
            throw new IllegalStateException(
                String.format("Invalid document status transition from %s to %s", current, next)
            );
        }
    }
}
