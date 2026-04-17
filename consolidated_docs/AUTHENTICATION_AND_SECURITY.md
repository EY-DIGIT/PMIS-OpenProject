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
    "user": { "_type": "User", ... }
  }
}
```

### Using Tokens
Include in all protected requests: `Authorization: Bearer <access_token>`

### Token Details
- Algorithm: HS256
- Access Token TTL: 15 minutes (configurable)
- Refresh Token TTL: 7 days
- JWT Payload: user_id, sub (login), role, is_admin, exp, iat
- Refresh token tracked via JTI stored in users table

### Token Introspection
POST /api/v3/users/introspect - Check token validity, optionally refresh

## Password Security
- Hashing: Argon2id (with bcrypt fallback)
- Minimum length: 8 characters
- Automatic salting with Argon2id
- Never stored or returned in plaintext

## Middleware Stack
1. CORSMiddleware - CORS configuration (allow_origins from settings)
2. LoggingMiddleware - Request/response logging, X-Request-ID header
3. AuthenticationMiddleware - JWT extraction and validation from Authorization header, sets request.state: user_id, user_login, user_role, is_admin

## RBAC (Role-Based Access Control)

### Roles
- ADMIN: Full system access
- MEMBER: Create, read, update most resources
- VIEWER: Read-only access
- ANONYMOUS: No access (unauthenticated)

### Permission Enforcement
- Route-level via `require_permission(Permission)` dependency
- Services and controllers do NOT check permissions
- All RBAC rules centralized in `app/core/rbac.py`

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
- Authenticated but insufficient permissions
- Fix: Verify user role has required permission in app/core/rbac.py

### Token not being sent in Swagger
- Fix: Click Authorize button, paste token without "Bearer" prefix

### Authorize button not showing
- Fix: Hard refresh browser (Ctrl+F5)
