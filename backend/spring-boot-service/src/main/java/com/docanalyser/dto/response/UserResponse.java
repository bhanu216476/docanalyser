package com.docanalyser.dto.response;

import java.util.UUID;

public class UserResponse {
    private UUID id;
    private String name;
    private String email;
    private String role;
    private String profileType;
    private String degree;
    private String branch;
    private String studyYear;

    public UserResponse(UUID id, String name, String email, String role, String profileType, String degree, String branch, String studyYear) {
        this.id = id;
        this.name = name;
        this.email = email;
        this.role = role;
        this.profileType = profileType;
        this.degree = degree;
        this.branch = branch;
        this.studyYear = studyYear;
    }

    public UUID getId() { return id; }
    public void setId(UUID id) { this.id = id; }
    public String getName() { return name; }
    public void setName(String name) { this.name = name; }
    public String getEmail() { return email; }
    public void setEmail(String email) { this.email = email; }
    public String getRole() { return role; }
    public void setRole(String role) { this.role = role; }
    public String getProfileType() { return profileType; }
    public void setProfileType(String profileType) { this.profileType = profileType; }
    public String getDegree() { return degree; }
    public void setDegree(String degree) { this.degree = degree; }
    public String getBranch() { return branch; }
    public void setBranch(String branch) { this.branch = branch; }
    public String getStudyYear() { return studyYear; }
    public void setStudyYear(String studyYear) { this.studyYear = studyYear; }
}
