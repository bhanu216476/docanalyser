package com.docanalyser.redis;

import com.docanalyser.entity.DocumentStatus;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class DocumentStateMachineTest {

    @Test
    @DisplayName("null -> UPLOADED or PENDING is allowed for initial creation")
    void initialCreation_validTransitions() {
        assertThat(DocumentStateMachine.isValidTransition(null, DocumentStatus.UPLOADED)).isTrue();
        assertThat(DocumentStateMachine.isValidTransition(null, DocumentStatus.PENDING)).isTrue();
        assertThat(DocumentStateMachine.isValidTransition(null, DocumentStatus.PROCESSING)).isFalse();
        assertThat(DocumentStateMachine.isValidTransition(null, DocumentStatus.INDEXED)).isFalse();
        assertThat(DocumentStateMachine.isValidTransition(null, DocumentStatus.FAILED)).isFalse();
    }

    @ParameterizedTest
    @CsvSource({
            "UPLOADED, PROCESSING",
            "PROCESSING, INDEXED",
            "PROCESSING, FAILED",
            "PROCESSING, READY",
            "PROCESSING, PROCESSED",
            "FAILED, PROCESSING",
            "PENDING, UPLOADED",
            "PENDING, PROCESSING"
    })
    @DisplayName("Valid forward lifecycle transitions are permitted")
    void validTransitions(DocumentStatus from, DocumentStatus to) {
        assertThat(DocumentStateMachine.isValidTransition(from, to)).isTrue();
        assertThatCode(() -> DocumentStateMachine.validateTransition(from, to)).doesNotThrowAnyException();
    }

    @ParameterizedTest
    @CsvSource({
            "UPLOADED, UPLOADED",
            "PROCESSING, PROCESSING",
            "INDEXED, INDEXED",
            "FAILED, FAILED"
    })
    @DisplayName("Idempotent transitions to same status are permitted")
    void idempotentTransitions(DocumentStatus from, DocumentStatus to) {
        assertThat(DocumentStateMachine.isValidTransition(from, to)).isTrue();
    }

    @ParameterizedTest
    @CsvSource({
            "INDEXED, UPLOADED",
            "INDEXED, PROCESSING",
            "INDEXED, FAILED",
            "READY, PROCESSING",
            "PROCESSED, PROCESSING",
            "UPLOADED, INDEXED",
            "UPLOADED, FAILED",
            "FAILED, INDEXED",
            "FAILED, UPLOADED"
    })
    @DisplayName("Invalid transitions are rejected with IllegalStateException")
    void invalidTransitions_areRejected(DocumentStatus from, DocumentStatus to) {
        assertThat(DocumentStateMachine.isValidTransition(from, to)).isFalse();
        assertThatThrownBy(() -> DocumentStateMachine.validateTransition(from, to))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("Invalid document status transition from " + from + " to " + to);
    }
}
