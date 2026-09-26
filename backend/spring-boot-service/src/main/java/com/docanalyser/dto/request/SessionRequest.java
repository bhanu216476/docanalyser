package com.docanalyser.dto.request;

import jakarta.validation.constraints.NotBlank;

public class SessionRequest {
    @NotBlank
    private String title;

    public String getTitle() { return title; }
    public void setTitle(String title) { this.title = title; }
}
