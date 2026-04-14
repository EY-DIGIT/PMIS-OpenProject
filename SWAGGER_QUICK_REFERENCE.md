# Swagger UI Authentication - Quick Reference Guide

## How to Use Protected Endpoints in Swagger UI

### Step 1: Access Swagger UI

```
http://localhost:8000/docs
```

### Step 2: Authorize (Get Token)

**Method A: Using the "Authorize" Button**

1. Click the green "Authorize" button (top-right)
2. A dialog opens asking for token
3. Go to Step 3 to get a token
4. Paste token and click "Authorize"

**Method B: Get Token First**

1. Find the `POST /api/v3/users/login` endpoint
2. Click "Try it out"
3. Enter credentials:
   ```json
   {
     "login": "admin",
     "password": "admin123"
   }
   ```
4. Click "Execute"
5. Copy the `access_token` from response
6. Click "Authorize" button
7. Paste token (without "Bearer" prefix)
8. Click "Authorize" in dialog

### Step 3: Test Protected Endpoints

Once authorized:

1. Find any endpoint with a **:lock: lock icon**
2. Click on it to expand
3. Click "Try it out"
4. Fill in parameters if needed
5. Click "Execute"
6. Response appears below

### Example: Get Current User

```
1. Click "Authorize" → Enter token → Confirm
2. Find "GET /api/v3/users/me"
3. Click endpoint to expand
4. Click "Try it out"
5. Click "Execute"
6. See user details in response
```

## Token Format

**In Swagger UI Authorize Dialog:**

```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
(just the token, without "Bearer" prefix)
```

**In actual HTTP requests:**

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
(includes "Bearer" prefix)
```

**In curl:**

```bash
curl -X GET "http://localhost:8000/api/v3/users/me" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

## Endpoint Categories

### Public Endpoints (No Auth Needed)

```
✓ GET    /health
✓ GET    /
✓ POST   /api/v3/users/login
✓ POST   /api/v3/users/introspect
```

### Protected Endpoints (Auth Required)

```
🔒 GET    /api/v3/users/me
🔒 GET    /api/v3/users
🔒 GET    /api/v3/users/{id}
🔒 POST   /api/v3/users
🔒 PATCH  /api/v3/users/{id}
🔒 DELETE /api/v3/users/{id}

🔒 GET    /api/v3/projects
🔒 POST   /api/v3/projects
🔒 GET    /api/v3/projects/{id}
🔒 PATCH  /api/v3/projects/{id}
🔒 DELETE /api/v3/projects/{id}

🔒 GET    /api/v3/meetings/{id}
🔒 POST   /api/v3/projects/{id}/meetings
🔒 PATCH  /api/v3/meetings/{id}
🔒 DELETE /api/v3/meetings/{id}
... and more
```

## Common Issues & Solutions

### "401 Unauthorized"

- **Cause**: Token missing or expired
- **Fix**: Click Authorize again and enter valid token

### "Token Not Being Sent"

- **Cause**: Not authorized in Swagger
- **Fix**: Click Authorize button and complete authorization

### "Cannot Test Endpoint"

- **Cause**: Missing required parameters
- **Fix**: Fill in all required fields marked with \*

### "Authorize Button Not Showing"

- **Cause**: Browser cache
- **Fix**: Hard refresh (Ctrl+F5) and try again

## Tips & Tricks

💡 **Token Persistence**

- Token is saved locally in browser
- Can refresh page without losing token
- Use incognito mode to clear token

💡 **Multiple Tokens**

- Click Authorize again to use different token
- Previous token is replaced

💡 **Response Inspection**

- Scroll down to see full response
- Click "Response headers" to see headers
- Check "Request" tab to see sent data

💡 **Try It Out Disabled?**

- Click the blue "Try it out" button at top-right of endpoint
- Or scroll to find it within response

## Request/Response Example

### Request (Shown in Swagger)

```json
Method: GET
URL: /api/v3/users/me
Headers:
  Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
  Content-Type: application/json
```

### Response (Shown in Swagger)

```json
{
  "data": {
    "_type": "User",
    "id": 1,
    "login": "admin",
    "email": "admin@example.com",
    "firstName": "Admin",
    "lastName": "User",
    "admin": true,
    "status": "active",
    "createdAt": "2025-12-15T11:26:26.833674",
    "updatedAt": "2025-12-15T11:26:26.833674",
    "_links": {
      "self": {
        "href": "/api/v3/users/1",
        "title": "admin"
      }
    }
  },
  "message": null,
  "error": null,
  "status": 200
}
```

## Default Test Credentials

```
Login: admin
Password: admin123
Email: admin@example.com
```

## Related Documentation

- **Full Details**: See `SWAGGER_AUTHENTICATION_UPDATE.md`
- **API Reference**: See `explanation docs/MASTER_CONSOLIDATED_DOCUMENT.md`
- **Implementation**: See `app/main.py` lines 132-176
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

---

**Last Updated**: April 13, 2026
