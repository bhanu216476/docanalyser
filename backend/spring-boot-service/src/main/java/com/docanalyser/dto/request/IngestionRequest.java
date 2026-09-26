package com.docanalyser.dto.request;

import jakarta.validation.constraints.NotBlank;

public class IngestionRequest {
    @NotBlank
    private String documentId;

    @NotBlank
    private String fileName;

    @NotBlank
    private String source;

    @NotBlank
    private String fileUrl;

    public String getDocumentId() { return documentId; }
    public void setDocumentId(String documentId) { this.documentId = documentId; }
    public String getFileName() { return fileName; }
    public void setFileName(String fileName) { this.fileName = fileName; }
    public String getSource() { return source; }
    public void setSource(String source) { this.source = source; }
    public String getFileUrl() { return fileUrl; }
    public void setFileUrl(String fileUrl) { this.fileUrl = fileUrl; }
}
