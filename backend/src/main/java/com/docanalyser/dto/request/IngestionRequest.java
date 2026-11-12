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

    private String contentHash;
    private String fileData;
    private Long fileSize;
    private String mimeType;
    private String ownerId;

    public String getDocumentId() { return documentId; }
    public void setDocumentId(String documentId) { this.documentId = documentId; }
    public String getFileName() { return fileName; }
    public void setFileName(String fileName) { this.fileName = fileName; }
    public String getSource() { return source; }
    public void setSource(String source) { this.source = source; }
    public String getFileUrl() { return fileUrl; }
    public void setFileUrl(String fileUrl) { this.fileUrl = fileUrl; }

    public String getContentHash() { return contentHash; }
    public void setContentHash(String contentHash) { this.contentHash = contentHash; }

    public String getFileData() { return fileData; }
    public void setFileData(String fileData) { this.fileData = fileData; }

    public Long getFileSize() { return fileSize; }
    public void setFileSize(Long fileSize) { this.fileSize = fileSize; }

    public String getMimeType() { return mimeType; }
    public void setMimeType(String mimeType) { this.mimeType = mimeType; }

    public String getOwnerId() { return ownerId; }
    public void setOwnerId(String ownerId) { this.ownerId = ownerId; }
}
