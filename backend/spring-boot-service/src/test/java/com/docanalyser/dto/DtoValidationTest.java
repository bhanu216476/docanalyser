package com.docanalyser.dto;

import com.docanalyser.dto.request.QueryRequest;
import jakarta.validation.ConstraintViolation;
import jakarta.validation.Validation;
import jakarta.validation.Validator;
import jakarta.validation.ValidatorFactory;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class DtoValidationTest {

    private static Validator validator;

    @BeforeAll
    static void setUpValidator() {
        ValidatorFactory factory = Validation.buildDefaultValidatorFactory();
        validator = factory.getValidator();
    }

    @Test
    void testValidQueryRequest() {
        QueryRequest request = new QueryRequest("What is the leave policy?");
        Set<ConstraintViolation<QueryRequest>> violations = validator.validate(request);
        assertTrue(violations.isEmpty());
    }

    @Test
    void testNullQueryRequest() {
        QueryRequest request = new QueryRequest(null);
        Set<ConstraintViolation<QueryRequest>> violations = validator.validate(request);
        assertEquals(1, violations.size());
        assertEquals("Query must not be blank", violations.iterator().next().getMessage());
    }

    @Test
    void testBlankQueryRequest() {
        QueryRequest request = new QueryRequest("   ");
        Set<ConstraintViolation<QueryRequest>> violations = validator.validate(request);
        assertEquals(1, violations.size());
        assertEquals("Query must not be blank", violations.iterator().next().getMessage());
    }

    @Test
    void testQueryExceedingMaxLength() {
        String longQuery = "a".repeat(1001);
        QueryRequest request = new QueryRequest(longQuery);
        Set<ConstraintViolation<QueryRequest>> violations = validator.validate(request);
        assertEquals(1, violations.size());
        assertEquals("Query must not exceed 1000 characters", violations.iterator().next().getMessage());
    }
}
