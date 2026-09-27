package com.docanalyser.auth;

public class RagServiceException extends RuntimeException {
    private final int statusCode;

    public RagServiceException(String message, int statusCode, Throwable cause) {
        super(message, cause);
        this.statusCode = statusCode;
    }

    public int getStatusCode() {
        return statusCode;
    }
}