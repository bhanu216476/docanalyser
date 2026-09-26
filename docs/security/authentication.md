# Authentication — JWT Flow

## Overview

DocAnalyser uses **stateless JWT (JSON Web Token) authentication** via Spring Security.  
No server-side session state is maintained. Every protected request must carry a valid Bearer token in the `Authorization` header.

---

## Token Lifecycle

```
┌──────────┐   POST /api/auth/register   ┌────────────────┐
│  Client  │ ─────────────────────────▶  │  Spring Boot   │
│          │   POST /api/auth/login       │                │
│          │ ─────────────────────────▶  │  BCrypt verify │
│          │   ◀─ { token, userId, ... }  │  JWT.create()  │
│          │                             └────────────────┘
│          │   GET /api/... (Bearer token)
│          │ ─────────────────────────▶  ┌────────────────┐
│          │   ◀─ Protected response      │ JwtAuthFilter  │
│          │                             │ validate token │
└──────────┘                             │ set SecurityCtx│
                                         └────────────────┘
```

---

## Registration

**Endpoint:** `POST /api/auth/register`

**Request body:**
```json
{
  "name": "Jane Doe",
  "email": "jane@example.com",
  "password": "securePassword123"
}
```

**Validation:**
- `email` — valid email format, required
- `password` — minimum 8 characters, required
- `name` — required

**Response:** `201 Created` (empty body on success)

**Error responses:**
| Status | Condition |
|--------|-----------|
| `400` | Validation failure (bad email, short password) |
| `409` | Email already registered |

---

## Login

**Endpoint:** `POST /api/auth/login`

**Request body:**
```json
{
  "email": "jane@example.com",
  "password": "securePassword123"
}
```

**Response:** `200 OK`
```json
{
  "token": "<JWT>",
  "userId": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Jane Doe",
  "email": "jane@example.com",
  "role": "USER"
}
```

**Error responses:**
| Status | Condition |
|--------|-----------|
| `400` | Missing or invalid fields |
| `401` | Bad credentials |

---

## Using the Token

Include the token in every protected request as a Bearer header:

```
Authorization: Bearer <JWT>
```

---

## Get Current User

**Endpoint:** `GET /api/auth/me`  
**Auth required:** Yes

**Response:** `200 OK`
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Jane Doe",
  "email": "jane@example.com",
  "role": "USER"
}
```

---

## Token Format & Signing

- **Algorithm:** HMAC256 (HS256)
- **Library:** `com.auth0:java-jwt:4.4.0`
- **Claims:**
  - `sub` — user email
  - `userId` — UUID string
  - `role` — role name without `ROLE_` prefix (e.g. `USER`, `ADMIN`)
  - `iat` — issued-at timestamp
  - `exp` — expiry timestamp

**Configuration (environment variables):**

| Variable | Default | Description |
|----------|---------|-------------|
| `JWT_SECRET` | *(required in prod)* | HMAC256 signing secret (min 32 chars) |
| `JWT_EXPIRATION_MS` | `86400000` (24 h) | Token validity in milliseconds |

> **Never commit a real JWT_SECRET to version control.**
> Use the .env.example as a template and set real values only in production secrets managers.

---

## Filter Chain

`JwtAuthenticationFilter` runs **before** `UsernamePasswordAuthenticationFilter`:

1. Extract `Authorization: Bearer <token>` header
2. Call `JwtUtils.validateJwtToken(token)`
3. Call `JwtUtils.getUsernameFromJwtToken(token)` -- email
4. Load `UserDetails` via `UserDetailsServiceImpl`
5. Set `UsernamePasswordAuthenticationToken` in `SecurityContextHolder`
6. Continue filter chain

Unauthenticated requests to protected endpoints return `401` via `AuthEntryPointJwt` (JSON response, not HTML redirect).

---

## Public Endpoints (no auth required)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/register` | POST | User registration |
| `/api/auth/login` | POST | Login + token issuance |
| `/api/health` | GET | Health check |
| `/actuator/**` | GET | Spring Actuator endpoints |
