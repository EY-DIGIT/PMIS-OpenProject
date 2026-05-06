# Authentication and Security Guide

## Authentication Flow

### Login

**`POST /api/v3/users/login`** with `{"login": "admin", "password": "admin123"}`

Two response shapes depending on whether 2FA is required for the user (per-user `users.two_factor_enabled` flag, gated globally by the `REQUIRE_2FA` env var — both default to true since doc 33 change 3):

**Shape A — single-stage (2FA disabled)**:
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

**Shape B — 2FA challenge (doc 33 change 3)**:
```json
{
  "data": {
    "_type": "LoginOtpRequired",
    "requires_otp": true,
    "ephemeral_token": "<opaque session handle>",
    "channels_available": ["email", "sms"],
    "message": "Two-factor authentication required. Choose a channel and request an OTP."
  }
}
```

The FE branches on `requires_otp`. When present, the JWT pair is **not** issued yet — the client follows up with `/login/send-otp` and `/login/verify-otp` (next section). The `ephemeral_token` is opaque, single-use per OTP, and only valid for the duration of the OTP session.

The `*ExpiresAt` / `expiresInSeconds` fields on Shape A let the FE schedule a preemptive call to `/users/refresh` without having to decode the JWT.

### Two-factor login (doc 33 change 3)

When `/login` returns Shape B, complete the flow in two more calls.

**Step 1 — `POST /api/v3/users/login/send-otp`**

Body:
```json
{
  "ephemeral_token": "<from /login response>",
  "channel": "email"   // or "sms"
}
```

Response:
```json
{
  "data": {
    "_type": "OtpSent",
    "channel": "email",
    "expires_in_seconds": 300,
    "resend_after_seconds": 60
  }
}
```

The OTP code itself is **never returned in the HTTP response** — even with `NOTIFICATION_CLIENT=mock`. In mock mode the dispatched payload (including the plaintext code) is recorded in the `notification_log` table; read it via DB during dev:
```sql
SELECT payload FROM notification_log
 WHERE template_kind = 'otp_login' AND user_id = '<user_uuid>'
 ORDER BY created_at DESC LIMIT 1;
```
With `NOTIFICATION_CLIENT=http`, the code is dispatched to the configured notification microservice and read by the user from email / SMS.

Resend behavior — calls within `OTP_RESEND_COOLDOWN_SECONDS` (default 60) return **429** with the seconds-remaining message. Each successful send writes a row to `notification_log` (channel, recipient, template_kind=`otp_login`, status).

**Step 2 — `POST /api/v3/users/login/verify-otp`**

Body:
```json
{
  "ephemeral_token": "<same as send-otp>",
  "code": "123456"
}
```

Response on success: identical to Shape A above (real JWT pair).

Failure modes — all 401:
- Wrong code → attempt counter increments; after `OTP_MAX_ATTEMPTS` (default 5) the OTP row is consumed and the user must restart from `/login`.
- Expired (older than `OTP_TTL_SECONDS`, default 300) → error message says expired.
- Already verified (single-use) → error message says consumed.

### 2FA per-user toggle

Admin updates a user's flag via `PATCH /api/v3/users/{user_id}` (permission: `users:update`):
```json
{ "twoFactorEnabled": false }
```

Disabling per-user is the supported way to opt service accounts / on-call automation out of the OTP step. To disable globally for an environment, set `REQUIRE_2FA=false`.

### Forgot-password / reset-password (doc 33 change 3)

Self-service reset, anti-enumeration: the `/forgot-password` endpoint always returns 200 regardless of whether the account exists.

**Step 1 — `POST /api/v3/users/forgot-password`**

Body:
```json
{
  "login_or_email": "admin",
  "channel": "email"   // or "sms"
}
```

Response (always 200, regardless of whether the account exists):
```json
{
  "data": {
    "_type": "PasswordResetRequested",
    "message": "If the account exists, a reset link or code has been dispatched."
  }
}
```

When the account exists, the server generates either:
- **email channel** — a URL-safe token (long random string) sent via the email template `password_reset_link`.
- **sms channel** — a 6-digit OTP sent via the template `password_reset_otp`.

Both forms are hashed (HMAC-SHA256 with `OTP_HASH_PEPPER` falling back to `SECRET_KEY`) and stored in `password_reset_tokens`. Plaintext only exists in transit / in the notification payload.

**Step 2 — `POST /api/v3/users/reset-password`**

Body:
```json
{
  "token_or_code": "<URL token from email OR 6-digit OTP from SMS>",
  "new_password": "newSecret123"
}
```

Response:
```json
{
  "data": {
    "_type": "ResetPasswordSuccess",
    "message": "Password reset successfully."
  }
}
```

Failure modes — all 401:
- Token expired (older than `PASSWORD_RESET_TTL_SECONDS`, default 3600 / 1 hour).
- Token invalid (wrong value or corrupted).
- Token already consumed (single-use).

`new_password` is validated by Pydantic: `min_length=8`, `max_length=255`. Successful reset clears the user's refresh-token slots so existing sessions are invalidated; the user must log in fresh.

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
  "userId": "8bd99f06-5f2a-424c-aaff-10ab163c3e42", "email": "admin@example.com",
  "role": null, "isAdmin": true
}
```

> **Doc 26**: `userId` is a UUID string (not an integer). Pre-doc-26 tokens carrying an integer `user_id` introspect to `{active: false}` (200, not 401) — same response shape, no special-casing needed by the FE.

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

## RBAC (DB-driven, doc 21B + doc 33 change 1/2)

### Model

- **Permissions** are string codes (`projects:create`, `master_data:manage`, `rbac:assign`, …). The canonical list lives in [app/core/permissions.py](../app/core/permissions.py); each code is upserted into the `permissions` table on every boot. Runtime additions land via `POST /api/v3/master/permissions/create` (doc 21B) and show up in the catalog without a redeploy.
- **Roles** are arbitrary named bundles. **Four** are seeded (doc 33 change 1 added vendor):
  - **`admin`** — auto-syncs to hold every registered permission. Cannot be deleted, renamed, or have its permission set changed via the API. Holders bypass nothing structurally — they simply hold every code.
  - **`member`** — default contributor set (CRUD on M/A/T/S, read on master data).
  - **`viewer`** — read-only.
  - **`vendor` (doc 33 change 1)** — external collaborator. Holds CRUD on milestones, activities, tasks, subtasks, comments, attachments, and `projects:read` only. Excludes lifecycle (`projects:create`/`publish`/`close`/`delete_all`), all of `rbac:*` / `roles:*` / `permissions:*`, master_data, users management, work_packages, and meeting writes. Assigned via the existing `POST /api/v3/users/{id}/roles/{role_id}` endpoint.
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
| `GET /api/v3/master/permissions` | Browse the permission catalog (flat) |
| `GET /api/v3/master/permissions/by-module` | **Doc 33 change 2** — same catalog grouped by module prefix (`projects`, `users`, `milestones`, …). FE picker UIs render module → permission tree from this. |
| `POST /api/v3/master/permissions/create` | Add a runtime permission (doc 21B). Built-ins are protected from edit/delete. |
| `GET /api/v3/master/roles` | Browse roles (admin/member/viewer/**vendor**) |
| `PUT /api/v3/master/roles/{id}/permissions` | Replace a role's permission set |
| `POST/DELETE /api/v3/users/{id}/roles/{role_id}` | Assign / unassign a role |
| `POST/DELETE /api/v3/users/{id}/permissions/{code}` | Direct grant / revoke |

## Cascade + dependency-block on delete (doc 34)

- **Cascade soft-delete** — deleting a milestone / activity / task / subtask soft-deletes every descendant + every comment + every attachment under the subtree (including comment-bound attachments via `attachments.comment_id`). Project delete cascades the whole project.
- **External-dependency block** — the M/A/T/S delete is refused with **422 `dependency_block`** when any entity inside the subtree is the target of a live dep edge whose source lives outside the subtree. The error response carries `_embedded.details.blockers: [{source, sourceKind, target, targetKind}, …]` so the FE can list "remove these deps before retrying". Self-contained deps (source + target both in the subtree) don't block. Project delete is exempt — deps are project-scoped.
- **Cascade restore** — restoring an M/A/T/S also restores every descendant + comment + attachment whose `deleted_at` exactly matches the cascade timestamp. Independently soft-deleted rows stay dead. Dep edges are NOT auto-restored — re-establish via PATCH `dependsOn`.

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
- POST /api/v3/users/login/send-otp     (doc 33 change 3 — gated by ephemeral_token)
- POST /api/v3/users/login/verify-otp   (doc 33 change 3 — gated by ephemeral_token + OTP)
- POST /api/v3/users/forgot-password    (doc 33 change 3 — anti-enumeration, always 200)
- POST /api/v3/users/reset-password     (doc 33 change 3 — gated by reset token)
- POST /api/v3/users/introspect
- POST /api/v3/users/refresh            (gated by refresh token)

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

## Doc 33 change 3 — env-var reference

| Setting | Default | Purpose |
|---|---|---|
| `REQUIRE_2FA` | `true` | Global on/off for the OTP step at login. Per-user override via `users.two_factor_enabled=false`. |
| `OTP_TTL_SECONDS` | `300` | OTP validity window (seconds). |
| `OTP_RESEND_COOLDOWN_SECONDS` | `60` | Min seconds between `/login/send-otp` resends per ephemeral session. Earlier resends → 429. |
| `OTP_MAX_ATTEMPTS` | `5` | Wrong-code attempts before the OTP row is invalidated. |
| `OTP_CODE_LENGTH` | `6` | Digits in the OTP. |
| `OTP_HASH_PEPPER` | `""` (falls back to `SECRET_KEY`) | Server-side pepper added to OTP / reset-token HMAC. |
| `PASSWORD_RESET_TTL_SECONDS` | `3600` | URL token / SMS OTP validity for `/forgot-password`. |
| `NOTIFICATION_CLIENT` | `mock` | `mock` writes to `notification_log` (DB sink); `http` POSTs to the real microservice. |
| `NOTIFICATION_SERVICE_URL` | `""` | Base URL of the notification microservice (used when `NOTIFICATION_CLIENT=http`). |

`notification_log` (table) records every dispatch — channel, recipient, template_kind (`otp_login` / `password_reset_link` / `password_reset_otp`), payload, status, error. There is no GET endpoint; inspect via DB during dev or operational triage.

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
- [ ] Set `OTP_HASH_PEPPER` to a deployment-unique value (don't fall back to `SECRET_KEY`)
- [ ] Switch `NOTIFICATION_CLIENT=http` and configure `NOTIFICATION_SERVICE_URL`
- [ ] Decide per-environment whether `REQUIRE_2FA=true` is acceptable (service accounts may need per-user opt-out)

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
