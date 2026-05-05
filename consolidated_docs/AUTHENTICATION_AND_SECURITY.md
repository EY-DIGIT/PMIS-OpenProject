# Authentication and Security Guide

## Authentication Flow

### Login
POST /api/v3/users/login with {"login": "admin", "password": "admin123"}

Returns:
```json
{
  "data": {
    "access_token": "eyJhbGc...",
    "token_type": "bearer",
    "refresh_token": "eyJhbGc...",
    "accessTokenExpiresAt":  "2026-04-28T18:15:00+00:00",
    "accessTokenIssuedAt":   "2026-04-28T18:00:00+00:00",
    "refreshTokenExpiresAt": "2026-05-05T18:00:00+00:00",
    "refreshTokenIssuedAt":  "2026-04-28T18:00:00+00:00",
    "expiresInSeconds": 900,
    "user": { "_type": "User", ... }
  }
}
```

The `*ExpiresAt` / `expiresInSeconds` fields let the FE schedule a
preemptive call to `/users/refresh` without having to decode the JWT.

### Using Tokens
Include in all protected requests: `Authorization: Bearer <access_token>`

### Token Details
- Algorithm: HS256
- Access Token TTL: 15 minutes (configurable via `ACCESS_TOKEN_EXPIRE_MINUTES`)
- Refresh Token TTL: 7 days (configurable via `REFRESH_TOKEN_EXPIRE_DAYS`)
- **JWT Payload (doc 21B): `sub` (login), `user_id`, `email`, `jti`, `iat`, `exp`** — `role` and `is_admin` are no longer carried; the auth middleware looks up the user's effective permission set from the DB on every request. Tokens issued before doc 21B that still carry `role`/`is_admin` keep working — those claims are simply ignored.
- **Doc 26: `user_id` is now a UUID string** (was an integer). Tokens minted before doc 26 carry an integer that no longer matches any `users.id` row — those users have to log in once to mint a fresh UUID-bearing token.
- Refresh token tracked via JTI stored in `users.refresh_token_jti` plus a 120-second grace slot (`previous_refresh_token_jti` + `previous_refresh_token_jti_valid_until`, doc 19) that lets a just-rotated-out token still satisfy a concurrent refresh / multi-tab login / stale retry.

### Token Introspection (RFC 7662, read-only)
**`POST /api/v3/users/introspect`** — pure metadata lookup. NEVER rotates.

Body: `{access_token?: string, refresh_token?: string}` (provide at least one).

Single-token response (flat):
```json
{
  "_type": "Introspect",
  "active": true,
  "tokenType": "access",
  "exp": 1714323300, "iat": 1714322400,
  "expiresAt": "2026-04-28T18:15:00+00:00",
  "issuedAt":  "2026-04-28T18:00:00+00:00",
  "jti": "...", "sub": "admin", "username": "admin",
  "userId": 1, "email": "admin@example.com",
  "role": null, "isAdmin": true
}
```

> Doc 21B: `role` is no longer a JWT claim and is returned as `null` for back-compat. `isAdmin` is resolved from the DB (membership in the `admin` role) at introspect time. Use `GET /api/v3/users/me/permissions` for the authoritative effective permission set.

Both-token response (split):
```json
{
  "_type": "Introspect",
  "access":  { "active": true,  "tokenType": "access",  ... },
  "refresh": { "active": true,  "tokenType": "refresh", ... }
}
```

Inactive / expired / revoked / unparseable token → `{"active": false, "tokenType": ...}` (200, not 401).

### Token Refresh (rotation)
**`POST /api/v3/users/refresh`** — validates the refresh token, swaps the
user row's stored jti atomically, and returns a fresh access + refresh pair.

Body: `{refresh_token: string}`

Response:
```json
{
  "_type": "Refresh",
  "access_token":  "eyJhbGc...",
  "refresh_token": "eyJhbGc...",
  "token_type": "bearer",
  "accessTokenExpiresAt":  "2026-04-28T18:30:00+00:00",
  "accessTokenIssuedAt":   "2026-04-28T18:15:00+00:00",
  "refreshTokenExpiresAt": "2026-05-05T18:15:00+00:00",
  "refreshTokenIssuedAt":  "2026-04-28T18:15:00+00:00",
  "expiresInSeconds": 900,
  "user": { "_type": "User", ... }
}
```

After a successful refresh, the previous JTI is held in a **grace slot**
on the user row for `REFRESH_TOKEN_GRACE_SECONDS` (default 120 — doc 19).
During the grace window either the current OR the previous JTI is
accepted, so a concurrent refresh / multi-tab login / stale retry
queued before the rotation no longer 401s. Outside the window, only
the current JTI is valid.

Failure modes (401):
- Invalid / expired refresh token
- JTI matches neither the current nor the in-grace previous slot
- User has been logged out (logout clears all 4 refresh-tracking columns)
- Posting an access token where the refresh token is expected

## Password Security
- Hashing: Argon2id (with bcrypt fallback)
- Minimum length: 8 characters
- Automatic salting with Argon2id
- Never stored or returned in plaintext

## Middleware Stack
1. **CORSMiddleware** — CORS configuration (allow_origins from settings)
2. **LoggingMiddleware** — Request/response logging, X-Request-ID header
3. **AuthenticationMiddleware (doc 21B)** — JWT decode + revoked-jti blacklist check + per-request permission hydration. Sets `request.state`:
   - `user_id`, `user_login`, `token_jti`, `token_exp`
   - `user_permissions: Set[str]` — the user's effective permission set, resolved once per request from `RbacRepository.effective_permissions_for_user(user_id)` (one DB query)
   - `is_admin: bool` — derived from membership in the seeded `admin` role
   For anonymous / revoked / decode-failure requests, `user_id` is `None` and `user_permissions` is empty — every `require_permission` rejects with 401.

## RBAC (DB-driven, doc 21B)

### Model

- **Permissions** are string codes (`projects:create`, `master_data:manage`, `rbac:assign`, …). The canonical list lives in [app/core/permissions.py](../app/core/permissions.py); each code is upserted into the `permissions` table on every boot.
- **Roles** are arbitrary named bundles. Three are seeded:
  - **`admin`** — auto-syncs to hold every registered permission. Cannot be deleted, renamed, or have its permission set changed via the API. Holders bypass nothing structurally — they simply hold every code.
  - **`member`** — default contributor set (CRUD on M/A/T/S, read on master data).
  - **`viewer`** — read-only.
- **Users** can be assigned any number of roles via the `user_roles` table. Direct grants in `user_permissions` are additive on top of role-derived permissions. There is no deny semantics — to revoke, delete the row.
- **Effective permissions** = union of role-derived ∪ direct grants. Hydrated per request by the auth middleware.

### Lockout protections

- Removing the last user holding the `admin` role → 403.
- Deleting / renaming / mutating the `admin` role → 403.
- Self-delete or self-demote of a sole admin → 422.

### Permission Enforcement

- Route-level via `require_permission("module:action")` (string code) — accepts the legacy `Permission` enum too for back-compat.
- Services and controllers do NOT re-check permissions.
- The decorator does an `O(1)` lookup against `request.state.user_permissions`.

### Endpoints to know

| Endpoint | Purpose |
|---|---|
| `GET /api/v3/users/me/permissions` | Caller's effective permission set + `isAdmin` flag — FE uses this to draw UI |
| `GET /api/v3/master/permissions` | Browse the permission catalog |
| `GET /api/v3/master/roles` | Browse roles |
| `PUT /api/v3/master/roles/{id}/permissions` | Replace a role's permission set |
| `POST/DELETE /api/v3/users/{id}/roles/{role_id}` | Assign / unassign a role |
| `POST/DELETE /api/v3/users/{id}/permissions/{code}` | Direct grant / revoke |

## Swagger/OpenAPI Configuration

### What's Configured
- Bearer token security scheme in OpenAPI schema
- Lock icons on protected endpoints in Swagger UI
- Authorize button for token management
- Token persistence across page refresh (`persistAuthorization: true`)

### Public Endpoints (no auth required)
- GET /health
- GET /
- POST /api/v3/users/login
- POST /api/v3/users/introspect

### Using Swagger UI
1. Visit http://localhost:8000/docs
2. Find POST /api/v3/users/login, click "Try it out"
3. Enter credentials: login=admin, password=admin123
4. Execute and copy the access_token from response
5. Click green "Authorize" button (top-right)
6. Paste token (without "Bearer" prefix - UI adds it)
7. Click "Authorize" in dialog
8. Now test any protected endpoint - token is auto-included

### Alternative Documentation
- ReDoc: http://localhost:8000/redoc (read-only)
- OpenAPI JSON: http://localhost:8000/openapi.json

### Configuration (app/main.py)
The custom_openapi() function adds Bearer security scheme and auto-annotates protected endpoints.
To add public endpoints, modify the public_paths list in the function.

## Frontend Integration

### JavaScript Example
```javascript
async function login(login, password) {
  const response = await fetch('/api/v3/users/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ login, password })
  });
  const data = await response.json();
  localStorage.setItem('access_token', data.data.access_token);
  localStorage.setItem('refresh_token', data.data.refresh_token);
  return data.data.user;
}

async function apiCall(endpoint, method = 'GET', body = null) {
  const token = localStorage.getItem('access_token');
  const response = await fetch(`/api/v3${endpoint}`, {
    method,
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: body ? JSON.stringify(body) : null
  });
  return await response.json();
}
```

### Error Handling
- 401: Token missing or expired - redirect to login or refresh token
- 403: Insufficient permissions - show "access denied" message
- 404: Resource not found
- 422: Validation error - show field-level errors

## Production Security Checklist
- [ ] Change default admin credentials
- [ ] Set strong SECRET_KEY (32+ characters) via environment variable
- [ ] Use PostgreSQL instead of SQLite
- [ ] Enable HTTPS/TLS
- [ ] Configure rate limiting
- [ ] Set CORS_ORIGINS to specific domains only
- [ ] Consider disabling Swagger UI: set openapi_url=None
- [ ] Implement audit logging
- [ ] Monitor failed authentication attempts
- [ ] Set up account lockout after failed logins

## Troubleshooting

### 401 Unauthorized
- Token missing or expired
- Fix: Login again, copy new token, re-authorize in Swagger

### 403 Forbidden
- Authenticated but the required permission is not in the caller's effective set, OR a protection guard fired (admin role lockout, admin role mutation, last-admin removal).
- Fix: Inspect `GET /api/v3/users/me/permissions`. To grant the missing code, either assign a role that holds it (`POST /api/v3/users/{id}/roles/{role_id}`) or add a direct grant (`POST /api/v3/users/{id}/permissions/{code}`).

### Token not being sent in Swagger
- Fix: Click Authorize button, paste token without "Bearer" prefix

### Authorize button not showing
- Fix: Hard refresh browser (Ctrl+F5)
