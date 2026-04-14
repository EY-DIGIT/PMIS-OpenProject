# Swagger/OpenAPI Authentication Update

**Date**: April 13, 2026  
**Status**: ✅ COMPLETE  
**File Modified**: `app/main.py`

---

## Overview

The Swagger/OpenAPI documentation has been updated to properly display JWT Bearer token authentication requirements for all protected API endpoints.

## Changes Made

### Modified File: `app/main.py`

**What was changed:**

1. Enabled the previously commented OpenAPI security scheme configuration
2. Added Bearer token authentication scheme to the OpenAPI schema
3. Configured automatic security requirement annotation for protected endpoints

### Configuration Details

#### Security Scheme Definition

```python
openapi_schema["components"]["securitySchemes"] = {
    "bearer": {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": "JWT Bearer token. Obtain token via /api/v3/users/login"
    }
}
```

This configuration tells Swagger UI:

- Authentication type: HTTP Bearer
- Scheme: Bearer token
- Format: JWT (JSON Web Token)
- How to obtain token: Via the `/api/v3/users/login` endpoint

#### Public vs. Protected Endpoints

**Public Endpoints** (no authentication required):

- `GET /health` - Health check
- `GET /` - Root endpoint
- `POST /api/v3/users/login` - User authentication
- `POST /api/v3/users/introspect` - Token introspection

**Protected Endpoints** (require Bearer token in Authorization header):

- All other endpoints that use `require_authenticated()` or `require_permission()` dependencies

### Swagger UI Experience

When you visit `http://localhost:8000/docs`:

1. **Public Endpoints**: No lock icon, can be tested directly
2. **Protected Endpoints**: Lock icon (:lock:) appears next to the endpoint
3. **Authorize Button**: Green "Authorize" button appears at the top-right

#### Using Authorization in Swagger UI

1. Click the "Authorize" button at the top
2. Enter the JWT token you received from `/api/v3/users/login`
3. Format: `Bearer <your_token_here>` (the word "Bearer" is added automatically)
4. Click "Authorize"
5. Try protected endpoints - token will be automatically included

### Example Authorization Flow

#### Step 1: Login to get token

```bash
POST /api/v3/users/login
Content-Type: application/json

{
  "login": "admin",
  "password": "admin123"
}

Response:
{
  "data": {
    "token_type": "bearer",
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "...",
    "user": {...}
  }
}
```

#### Step 2: Use token with any protected endpoint

```bash
GET /api/v3/users/me
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

#### Step 3: In Swagger UI

- Copy the `access_token` value from login response
- Click "Authorize" button
- Paste token (without "Bearer" prefix, UI adds it automatically)
- All future requests in Swagger include the token

## Benefits

✅ **Clear Documentation**: Swagger UI visually indicates which endpoints require authentication  
✅ **Easy Testing**: Users can authorize once and test all protected endpoints  
✅ **Standards Compliant**: Follows OpenAPI 3.0 specification for Bearer authentication  
✅ **Token Management**: `persistAuthorization: true` keeps token after page refresh  
✅ **User Friendly**: Lock icons and Authorize button make authentication obvious

## Technical Details

### How It Works

The `custom_openapi()` function:

1. Generates the standard OpenAPI schema
2. Adds Bearer token security scheme definition
3. Iterates through all API paths
4. For non-public endpoints, adds `"security": [{"bearer": []}]` to each operation
5. Public endpoints explicitly excluded from auto-annotation

### Code Location

```
app/main.py
├── Lines 132-176: custom_openapi() function and configuration
```

### Public Endpoint List

Currently configured as public:

- `/health`
- `/`
- `/api/v3/users/login`
- `/api/v3/users/introspect`

To add additional public endpoints, modify line 163 in `app/main.py`:

```python
public_paths = ["/health", "/", "/api/v3/users/login", "/api/v3/users/introspect"]
```

## Testing

### Verification

Run this to verify the security scheme is configured:

```bash
cd C:\Programming\PMIS_Python

# Start the application
python -m uvicorn app.main:app --reload

# Visit Swagger UI
# http://localhost:8000/docs

# Or verify programmatically:
python -c "
from app.main import app
import json
openapi = app.openapi()
print(json.dumps(openapi['components']['securitySchemes'], indent=2))
"
```

### Verify in Swagger UI

1. Go to http://localhost:8000/docs
2. Look for lock icons next to protected endpoints
3. Click on a protected endpoint (e.g., GET /api/v3/users)
4. See "Authorization" header requirement in the documentation
5. Test by:
   - Clicking "Authorize" button
   - Logging in via POST /api/v3/users/login
   - Copying the token
   - Pasting in Authorize dialog
   - Testing the protected endpoint

### Expected Results

✅ Security scheme appears at top of Swagger page  
✅ Protected endpoints show lock icon  
✅ Authorize button is functional  
✅ Token persists across page refreshes  
✅ Requests include Authorization header when authenticated

## API Documentation

### Swagger UI

- **URL**: http://localhost:8000/docs
- **Format**: Interactive Swagger UI
- **Features**: Try-it-out, parameter validation, authentication

### ReDoc

- **URL**: http://localhost:8000/redoc
- **Format**: Read-only API documentation
- **Features**: Better for reading, shows security requirements

### OpenAPI JSON

- **URL**: http://localhost:8000/openapi.json
- **Format**: Raw OpenAPI 3.0 JSON schema
- **Use Case**: Integrations, code generation

## Configuration Options

### Swagger UI Parameters (in FastAPI app initialization)

Currently configured:

```python
swagger_ui_parameters={"persistAuthorization": True}
```

This means:

- `persistAuthorization: True` - Authorization token is saved across page refresh

Other useful options:

```python
swagger_ui_parameters={
    "persistAuthorization": True,     # Save auth token on refresh
    "defaultModelsExpandDepth": 2,    # Expand model examples
    "deepLinking": True,              # Deep link to specific operations
    "filter": False,                  # Disable search filter
    "layout": "BaseLayout"            # Use simple layout
}
```

## Troubleshooting

### Issue: "Authorize button not showing"

**Solution**: Clear browser cache and refresh (Ctrl+F5)

### Issue: "Token not being sent with requests"

**Solution**:

1. Click Authorize button again
2. Make sure token doesn't include "Bearer" prefix (UI adds it)
3. Verify token is valid (not expired)

### Issue: "401 Unauthorized after authorization"

**Cause**: Token may be expired  
**Solution**:

1. Log in again via POST /api/v3/users/login
2. Copy new access_token
3. Click Authorize again with new token

### Issue: "Security scheme not showing in ReDoc"

**Note**: ReDoc shows security requirements differently. Check the "Security" section at top.

## Best Practices

✅ **In Development**:

- Use Swagger UI at http://localhost:8000/docs
- Test all endpoints with Authorization
- Keep browser console open to monitor network requests

✅ **In Production**:

- Ensure HTTPS is enabled
- Consider disabling Swagger UI for security: `openapi_url=None`
- Use OpenAPI schema for client code generation
- Monitor failed authentication attempts

✅ **For API Users**:

1. First call: POST /api/v3/users/login with credentials
2. Store returned `access_token`
3. Include token in Authorization header: `Bearer <token>`
4. If token expires (401 response), refresh with refresh token
5. Repeat from step 2

## Summary

The Swagger/OpenAPI documentation now:

- ✅ Shows clear authentication requirements
- ✅ Provides built-in token management
- ✅ Displays lock icons for protected endpoints
- ✅ Offers easy testing with authorization
- ✅ Documents Bearer token JWT format
- ✅ Shows how to obtain tokens

**Status**: Ready for use. All protected endpoints now properly display authentication requirements in Swagger UI.

---

**Reference Documentation**:

- OpenAPI 3.0 Spec: https://spec.openapis.org/oas/v3.0.0#security-scheme-object
- FastAPI Security: https://fastapi.tiangolo.com/tutorial/security/
- JWT Bearer Tokens: https://tools.ietf.org/html/rfc6750
