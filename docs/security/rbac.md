# RBAC — Role-Based Access Control

## Overview

DocAnalyser implements a simple two-role RBAC system:

| Role | Description |
|------|-------------|
| `USER` | Standard user — can manage their own resources |
| `ADMIN` | Administrator — full read access to all resources |

Roles are stored in the `users.role` column as a `VARCHAR` enum (`USER` or `ADMIN`).  
A user is assigned `USER` by default at registration. Admin accounts must be created manually in the database or via a future admin provisioning endpoint.

---

## Permissions Matrix

| Resource / Action | USER | ADMIN |
|-------------------|------|-------|
| Register / Login | ✅ | ✅ |
| GET /api/auth/me | ✅ (own) | ✅ (own) |
| GET /api/documents | ✅ (own only) | ✅ (all) |
| GET /api/documents/{id} | ✅ (own only) | ✅ (any) |
| DELETE /api/documents/{id} | ✅ (own only) | ✅ (any) |
| GET /api/chat/sessions | ✅ (own only) | ✅ (own only) |
| POST /api/chat/sessions | ✅ | ✅ |
| GET /api/chat/sessions/{id} | ✅ (own only) | ✅ (own only) |
| POST /api/chat/sessions/{id}/messages | ✅ (own only) | ✅ (own only) |
| POST /api/internal/documents/ingest | ❌ | ❌ (system only) |

### Internal Endpoints

`/api/internal/**` endpoints are **not** protected by JWT. They use a separate `X-Internal-Token` header validated by `InternalApiKeyFilter`. This token is consumed exclusively by the n8n automation workflow and is never exposed to regular users.

---

## How Role Checks Work

### In Services (runtime RBAC)

`DocumentService` and `ChatService` perform manual checks using the `UserDetailsImpl` principal injected by Spring Security:

```java
// DocumentService.getDocuments()
boolean isAdmin = userDetails.getAuthorities().stream()
        .anyMatch(a -> a.getAuthority().equals("ROLE_ADMIN"));

if (isAdmin) {
    return documentRepository.findAll();
} else {
    return documentRepository.findByOwnerId(userDetails.getId());
}
```

### In Security Configuration

`SecurityConfig` declares:
- All routes under `/api/auth/**` and `/api/health` are public (`permitAll`)
- All other routes require authentication (`authenticated`)
- Internal routes (`/api/internal/**`) filtered via `InternalApiKeyFilter` before the JWT filter

---

## Adding a New Admin User

Until an admin provisioning UI is built, set a user's role directly in the database:

```sql
UPDATE users SET role = 'ADMIN' WHERE email = 'admin@example.com';
```

---

## Security Notes

- Roles are embedded in the JWT at login time. If a user's role changes in the DB, they must log in again for the new role to take effect.
- There is **no token revocation** mechanism in the current implementation. For revocation, consider adding a token blocklist (Redis or DB table).
- The `SYSTEM` role used by `InternalApiKeyFilter` is not a database role — it exists only as an in-memory Spring Security authority for the duration of the internal request.
