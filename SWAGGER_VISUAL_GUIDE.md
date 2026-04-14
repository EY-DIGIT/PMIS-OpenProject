# Swagger UI Visual Guide

## What Developers Will See

### 1. Swagger UI Home Page

```
http://localhost:8000/docs

┌─────────────────────────────────────────────────────────────┐
│ PMIS API (v3.0.0)                        [Authorize]  ⚙️    │  ← GREEN Authorize Button
│ OpenProject-compatible Project Management API...           │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│ Models                                                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ Servers: http://localhost:8000                             │
│                                                             │
│ health                                                      │
│ └─ [GET] /health         200 Health check                 │
│                                                             │
│ root                                                        │
│ └─ [GET] /                                                │
│                                                             │
│ users                                                       │
│ ├─ [POST] /api/v3/users/login                             │
│ ├─ [POST] /api/v3/users/introspect                        │
│ ├─ [GET] 🔒 /api/v3/users/me                              │  ← LOCK ICON
│ ├─ [GET] 🔒 /api/v3/users                                 │
│ ├─ [POST] 🔒 /api/v3/users                                │
│ ├─ [GET] 🔒 /api/v3/users/{id}                            │
│ ├─ [PATCH] 🔒 /api/v3/users/{id}                          │
│ ├─ [PATCH] 🔒 /api/v3/users/{id}/password                 │
│ └─ [DELETE] 🔒 /api/v3/users/{id}                         │
│                                                             │
│ projects                                                    │
│ ├─ [POST] 🔒 /api/v3/projects                             │
│ ├─ [GET] 🔒 /api/v3/projects                              │
│ ├─ [GET] 🔒 /api/v3/projects/{id}                         │
│ ├─ [PATCH] 🔒 /api/v3/projects/{id}                       │
│ └─ [DELETE] 🔒 /api/v3/projects/{id}                      │
│                                                             │
│ meetings                                                    │
│ ├─ [POST] 🔒 /api/v3/meetings/{id}                        │
│ ├─ [GET] 🔒 /api/v3/projects/{id}/meetings                │
│ └─ ... and more                                            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2. Authorize Dialog

When clicking the green "Authorize" button:

```
┌───────────────────────────────────────────┐
│ Available Authorizations                  │
├───────────────────────────────────────────┤
│                                           │
│ bearer (HTTP Bearer)                      │
│ ┌─────────────────────────────────────┐  │
│ │ eyJhbGciOiJIUzI1NiIsInR5cCI...      │  │
│ │                                     │  │
│ │ (Paste JWT token here, without     │  │
│ │  the "Bearer " prefix)             │  │
│ └─────────────────────────────────────┘  │
│                                           │
│                [Authorize]  [Logout]      │
│                                           │
│ HTTP Bearer: JWT Bearer token. Obtain   │
│ token via /api/v3/users/login          │
│                                           │
└───────────────────────────────────────────┘
```

### 3. Protected Endpoint Example

Clicking on a protected endpoint (e.g., GET /api/v3/users/me):

```
┌─────────────────────────────────────────────────────────────┐
│ GET /api/v3/users/me     🔒                                 │
│ Get current user                                            │
├─────────────────────────────────────────────────────────────┤
│ Authorizations required: bearer-auth                        │  ← Shows required auth
│                                                             │
│ [Try it out]                                               │
│                                                             │
│ curl -X GET "http://localhost:8000/api/v3/users/me" \     │
│   -H "accept: application/json" \                          │
│   -H "Authorization: Bearer YOUR_TOKEN_HERE"               │  ← Shows header format
│                                                             │
│ [Execute]                                                  │
│                                                             │
│ Response:                                                  │
│ ┌──────────────────────────────────────────────────────┐  │
│ │ Code: 200                                            │  │
│ │ {                                                    │  │
│ │   "data": {                                          │  │
│ │     "_type": "User",                                 │  │
│ │     "id": 1,                                         │  │
│ │     "login": "admin",                                │  │
│ │     "email": "admin@example.com",                    │  │
│ │     "admin": true,                                   │  │
│ │     ...                                              │  │
│ │   },                                                 │  │
│ │   "status": 200                                      │  │
│ │ }                                                    │  │
│ └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 4. Login Endpoint (Public - No Lock Icon)

```
┌─────────────────────────────────────────────────────────────┐
│ POST /api/v3/users/login                                    │
│ Authenticate user                                           │
├─────────────────────────────────────────────────────────────┤
│ No authorization required                                   │  ← No lock icon
│                                                             │
│ [Try it out]                                               │
│                                                             │
│ Request body:                                              │
│ ┌──────────────────────────────────────────────────────┐  │
│ │ {                                                    │  │
│ │   "login": "admin",                                  │  │
│ │   "password": "admin123"                             │  │
│ │ }                                                    │  │
│ └──────────────────────────────────────────────────────┘  │
│                                                             │
│ [Execute]                                                  │
│                                                             │
│ Response:                                                  │
│ ┌──────────────────────────────────────────────────────┐  │
│ │ Code: 200                                            │  │
│ │ {                                                    │  │
│ │   "data": {                                          │  │
│ │     "token_type": "bearer",                          │  │
│ │     "access_token": "eyJhbGciOiJIU...",             │  │  ← Copy this
│ │     "refresh_token": "...",                          │  │
│ │     "user": { ... }                                  │  │
│ │   },                                                 │  │
│ │   "status": 200                                      │  │
│ │ }                                                    │  │
│ └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Step-by-Step Usage Flow

### Flow 1: Quick Test (5 minutes)

```
1. Open Swagger UI
   ↓
2. Find POST /api/v3/users/login (PUBLIC)
   ↓
3. Click "Try it out"
   ↓
4. Enter login: "admin", password: "admin123"
   ↓
5. Click Execute
   ↓
6. Copy access_token from response
   ↓
7. Click green "Authorize" button
   ↓
8. Paste token in dialog
   ↓
9. Click "Authorize" in dialog
   ↓
10. Now find any 🔒 endpoint
   ↓
11. Click "Try it out"
   ↓
12. Click "Execute" - token is auto-included!
   ↓
13. See successful response
```

### Flow 2: Persistent Authorization (Better)

```
1. Open Swagger UI
   ↓
2. Click green "Authorize" button at top-right
   ↓
3. Get token from POST /api/v3/users/login endpoint
   ↓
4. Paste token in dialog
   ↓
5. Click "Authorize"
   ↓
6. (Token is saved in browser - persists on refresh!)
   ↓
7. Can now test ANY protected endpoint
   ↓
8. No need to manually add headers
   ↓
9. When token expires, repeat step 2-5
```

## Icon Legend

| Icon         | Meaning                            | Example                  |
| ------------ | ---------------------------------- | ------------------------ |
| 🔒           | Protected endpoint (requires auth) | GET 🔒 /api/v3/users/me  |
| (no icon)    | Public endpoint (no auth required) | POST /api/v3/users/login |
| [Authorize]  | Green button to set auth token     | Top-right of Swagger UI  |
| [Try it out] | Button to test endpoint            | In each endpoint section |
| [Execute]    | Button to send request             | Below parameters         |

## Common Actions in Swagger UI

### Action: Authorize Once, Test Multiple Endpoints

```
1. Click [Authorize] button
2. Get & paste token
3. Click "Authorize"
4. Open endpoint 1, click [Try it out] → [Execute]
5. Open endpoint 2, click [Try it out] → [Execute]
6. Open endpoint 3, click [Try it out] → [Execute]

← Token automatically included in all requests!
```

### Action: Check Request Headers

```
1. Run any request via Swagger UI
2. Scroll down to "Requests"
3. Click on it to expand
4. See: Authorization: Bearer eyJhbG...
5. Verify token was sent correctly
```

### Action: Inspect Full Response

```
1. Run a request
2. Scroll to "Response"
3. See status code and body
4. Click "Response headers" to see headers
5. See Content-Type, Date, etc.
```

## Troubleshooting Visual Clues

### Problem: Can't see Authorize button

**Visual**: Top-right button area is empty
**Fix**: Hard refresh (Ctrl+F5)

### Problem: Lock icons not showing

**Visual**: Endpoints show [GET] /api/v3/users, not [GET] 🔒 /api/v3/users
**Fix**: Clear cache, refresh page

### Problem: Getting 401 when testing

**Visual**: Response shows `{"error": {"message": "Unauthorized"}}`
**Fix**: Click Authorize again, verify token

### Problem: Token not being sent

**Visual**: Request header doesn't show "Authorization: Bearer..."
**Fix**: Verify you authorized (check for green "Authorize" button confirmation)

## API Version Info

Located at top of Swagger UI page:

```
PMIS API                          ← Application Name
v3.0.0                            ← Version
OpenProject-compatible...         ← Description
```

## ReDoc Alternative

If Swagger UI doesn't work well, try ReDoc:

```
http://localhost:8000/redoc

- Shows API documentation in cleaner format
- Can't test endpoints (read-only)
- Better for reading specs
- Security requirements clearly documented
```

## Raw OpenAPI Schema

For API code generation or other tools:

```
http://localhost:8000/openapi.json

Returns full OpenAPI 3.0 specification in JSON format.
Can be imported into Postman, generators, etc.
```

---

**Last Updated**: April 13, 2026  
**Status**: Production Ready
