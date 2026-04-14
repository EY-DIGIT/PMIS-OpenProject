# PMIS API Request/Response Flow Documentation

## Complete Request-Response Flows for Key Endpoints

### Overview
This document provides detailed request-response flows for all major API endpoints, including headers, payloads, and responses for frontend integration.

---

## Flow 1: User Authentication & Login

### Endpoint
```
POST /api/v3/users/login
```

### Request Details
```
Method: POST
URL: http://localhost:8000/api/v3/users/login
Content-Type: application/json
No Authorization Required
```

### Request Payload
```json
{
  "login": "admin",
  "password": "admin123"
}
```

### Request Validation
- **login**: Required, string, case-sensitive
- **password**: Required, string, minimum 8 characters

### Response Flow

#### Success (200 OK)
```json
{
  "status": 200,
  "message": "User authenticated successfully",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoxLCJleHAiOjE3NTA0OTI3NjUsImlhdCI6MTc1MDQ5MTg2NX0.AbcDefGhIjKlMnOpQrStUvWxYz...",
    "token_type": "bearer",
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoxLCJleHAiOjE3NTA5MDk5OTksImlhdCI6MTc1MDQ5MTg2NSwianRpIjoiYTk0MmM5MjI4YzUxNDM4NzlkNDU1ZDU1MzQ0YzAzODEifQ.XyZ..."
  },
  "error": null
}
```

#### Failure - Invalid Credentials (401 Unauthorized)
```json
{
  "status": 401,
  "message": "Invalid credentials",
  "data": null,
  "error": {
    "type": "AuthenticationError",
    "message": "Login failed - invalid login or password",
    "details": null
  }
}
```

#### Failure - Validation Error (422 Unprocessable Entity)
```json
{
  "status": 422,
  "message": "Validation failed",
  "data": null,
  "error": {
    "type": "ValidationError",
    "message": "Invalid request body",
    "details": {
      "field": "password",
      "issue": "ensure this value has at least 8 characters"
    }
  }
}
```

### Frontend Implementation
```javascript
// Login function
async function login(login, password) {
  try {
    const response = await fetch('/api/v3/users/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ login, password })
    });
    
    const data = await response.json();
    
    if (response.ok) {
      // Store tokens
      localStorage.setItem('access_token', data.data.access_token);
      localStorage.setItem('refresh_token', data.data.refresh_token);
      return { success: true, user: data.data };
    } else {
      return { success: false, error: data.error.message };
    }
  } catch (error) {
    return { success: false, error: error.message };
  }
}
```

---

## Flow 2: Get Current User

### Endpoint
```
GET /api/v3/users/me
```

### Request Details
```
Method: GET
URL: http://localhost:8000/api/v3/users/me
Content-Type: application/json
Authorization: Bearer <access_token>
```

### Request Headers
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoxLCJleHAiOjE3NTA0OTI3NjUsImlhdCI6MTc1MDQ5MTg2NX0.AbcDefGhIjKlMnOpQrStUvWxYz...
```

### Response - Success (200 OK)
```json
{
  "status": 200,
  "message": "User fetched successfully",
  "data": {
    "id": 1,
    "login": "admin",
    "email": "admin@example.com",
    "firstName": "Admin",
    "lastName": "User",
    "admin": true,
    "status": "active",
    "created_at": "2026-04-13T09:00:00Z",
    "updated_at": "2026-04-13T09:00:00Z"
  },
  "error": null
}
```

### Response - Missing Token (401 Unauthorized)
```json
{
  "status": 401,
  "message": "Authentication required",
  "data": null,
  "error": {
    "type": "AuthenticationError",
    "message": "Access token not found or invalid",
    "details": null
  }
}
```

### Response - Expired Token (401 Unauthorized)
```json
{
  "status": 401,
  "message": "Token has expired",
  "data": null,
  "error": {
    "type": "AuthenticationError",
    "message": "Access token has expired. Please use refresh token.",
    "details": null
  }
}
```

### Frontend Implementation
```javascript
async function getCurrentUser() {
  const token = localStorage.getItem('access_token');
  
  if (!token) {
    return { success: false, error: 'No token found' };
  }
  
  try {
    const response = await fetch('/api/v3/users/me', {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      }
    });
    
    const data = await response.json();
    
    if (response.ok) {
      return { success: true, user: data.data };
    } else if (response.status === 401) {
      // Token expired - try refreshing
      return { success: false, error: 'Token expired', expired: true };
    } else {
      return { success: false, error: data.error.message };
    }
  } catch (error) {
    return { success: false, error: error.message };
  }
}
```

---

## Flow 3: Create User

### Endpoint
```
POST /api/v3/users
```

### Request Details
```
Method: POST
URL: http://localhost:8000/api/v3/users
Content-Type: application/json
Authorization: Bearer <admin_token>
Required Permission: USERS_CREATE
```

### Request Payload
```json
{
  "login": "john.doe",
  "email": "john.doe@example.com",
  "password": "SecurePassword123!",
  "firstName": "John",
  "lastName": "Doe",
  "admin": false
}
```

### Request Validation Rules
```
Field: login
- Type: string
- Min Length: 3
- Max Length: 50
- Unique: Yes
- Pattern: alphanumeric, dash, underscore allowed

Field: email
- Type: string
- Format: Valid email (RFC 5322)
- Unique: Yes

Field: password
- Type: string
- Min Length: 8
- No special requirements

Field: firstName, lastName
- Type: string (optional)
- Max Length: 255

Field: admin
- Type: boolean
- Default: false
- Only admins can set this
```

### Response - Success (201 Created)
```json
{
  "status": 201,
  "message": "User created successfully",
  "data": {
    "id": 5,
    "login": "john.doe",
    "email": "john.doe@example.com",
    "firstName": "John",
    "lastName": "Doe",
    "admin": false,
    "status": "active",
    "created_at": "2026-04-13T10:30:45Z",
    "updated_at": "2026-04-13T10:30:45Z"
  },
  "error": null
}
```

### Response - Duplicate Login (409 Conflict)
```json
{
  "status": 409,
  "message": "User creation failed",
  "data": null,
  "error": {
    "type": "DuplicateError",
    "message": "User with login already exists",
    "details": {
      "field": "login",
      "value": "john.doe"
    }
  }
}
```

### Response - Insufficient Permissions (403 Forbidden)
```json
{
  "status": 403,
  "message": "Permission denied",
  "data": null,
  "error": {
    "type": "AuthorizationError",
    "message": "User does not have required permission: USERS_CREATE",
    "details": null
  }
}
```

### Response - Validation Error (422)
```json
{
  "status": 422,
  "message": "Validation failed",
  "data": null,
  "error": {
    "type": "ValidationError",
    "message": "Invalid request body",
    "details": [
      {
        "field": "email",
        "message": "invalid email format"
      },
      {
        "field": "password",
        "message": "ensure this value has at least 8 characters"
      }
    ]
  }
}
```

### Frontend Implementation
```javascript
async function createUser(userData) {
  const token = localStorage.getItem('access_token');
  
  try {
    const response = await fetch('/api/v3/users', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        login: userData.login,
        email: userData.email,
        password: userData.password,
        firstName: userData.firstName,
        lastName: userData.lastName,
        admin: userData.admin || false
      })
    });
    
    const data = await response.json();
    
    if (response.ok) {
      return { success: true, user: data.data };
    } else if (response.status === 409) {
      return { 
        success: false, 
        error: 'User already exists',
        field: data.error.details?.field 
      };
    } else if (response.status === 403) {
      return { success: false, error: 'Admin permission required' };
    } else {
      return { success: false, error: data.error.message };
    }
  } catch (error) {
    return { success: false, error: error.message };
  }
}
```

---

## Flow 4: List Projects with Pagination

### Endpoint
```
GET /api/v3/projects
```

### Request Details
```
Method: GET
URL: http://localhost:8000/api/v3/projects?offset=1&pageSize=20&active=true
Content-Type: application/json
Authorization: Bearer <token>
Required Permission: PROJECTS_READ
```

### Query Parameters
```
offset: 1 (Start from page 1)
pageSize: 20 (Items per page)
active: true (Optional filter)
public: false (Optional filter)
```

### Response - Success (200 OK)
```json
{
  "status": 200,
  "message": "Projects fetched successfully",
  "data": [
    {
      "id": 1,
      "identifier": "proj-2026-01",
      "name": "Q1 2026 Initiative",
      "description": "Quarterly planning and execution",
      "public": false,
      "active": true,
      "created_at": "2026-04-01T10:00:00Z",
      "updated_at": "2026-04-01T10:00:00Z"
    },
    {
      "id": 2,
      "identifier": "proj-2026-02",
      "name": "Q2 2026 Planning",
      "description": "Second quarter initiative",
      "public": true,
      "active": true,
      "created_at": "2026-04-05T14:22:00Z",
      "updated_at": "2026-04-05T14:22:00Z"
    }
  ],
  "error": null,
  "total": 25,
  "offset": 1,
  "limit": 20
}
```

### Response - No Results (200 OK)
```json
{
  "status": 200,
  "message": "Projects fetched successfully",
  "data": [],
  "error": null,
  "total": 0,
  "offset": 1,
  "limit": 20
}
```

### Frontend Implementation
```javascript
async function listProjects(offset = 1, pageSize = 20, filters = {}) {
  const token = localStorage.getItem('access_token');
  
  // Build query string
  const params = new URLSearchParams({
    offset,
    pageSize,
    ...filters
  });
  
  try {
    const response = await fetch(`/api/v3/projects?${params}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      }
    });
    
    const data = await response.json();
    
    if (response.ok) {
      return {
        success: true,
        projects: data.data,
        total: data.total,
        offset: data.offset,
        limit: data.limit,
        hasMore: data.total > (data.offset + data.limit)
      };
    } else {
      return { success: false, error: data.error.message };
    }
  } catch (error) {
    return { success: false, error: error.message };
  }
}

// Usage
const projectsData = await listProjects(1, 20, { active: true });
```

---

## Flow 5: Create Meeting

### Endpoint
```
POST /api/v3/projects/{project_id}/meetings
```

### Request Details
```
Method: POST
URL: http://localhost:8000/api/v3/projects/1/meetings
Content-Type: application/json
Authorization: Bearer <token>
Required Permission: MEETINGS_CREATE
Path Parameter: project_id = 1
```

### Request Payload
```json
{
  "title": "Q1 Budget Review Meeting",
  "description": "Review and finalize Q1 budget allocation across departments",
  "scheduled_at": "2026-05-15T10:00:00Z",
  "duration_minutes": 90,
  "location": "Conference Room A"
}
```

### Request Validation Rules
```
Field: title
- Type: string
- Min Length: 1
- Max Length: 255
- Required: Yes

Field: scheduled_at
- Type: ISO 8601 datetime string
- Format: "2026-05-15T10:00:00Z"
- Required: Yes

Field: duration_minutes
- Type: integer
- Min Value: 0
- Max Value: 10080 (1 week)
- Optional

Field: description
- Type: string
- Max Length: 5000
- Optional

Field: location
- Type: string
- Max Length: 255
- Optional
```

### Response - Success (201 Created)
```json
{
  "status": 201,
  "message": "Meeting created successfully",
  "data": {
    "id": 1,
    "project_id": 1,
    "title": "Q1 Budget Review Meeting",
    "description": "Review and finalize Q1 budget allocation across departments",
    "scheduled_at": "2026-05-15T10:00:00Z",
    "duration_minutes": 90,
    "location": "Conference Room A",
    "created_by_id": 1,
    "created_at": "2026-04-13T10:45:30Z",
    "updated_at": "2026-04-13T10:45:30Z"
  },
  "error": null
}
```

### Response - Project Not Found (404 Not Found)
```json
{
  "status": 404,
  "message": "Meeting creation failed",
  "data": null,
  "error": {
    "type": "NotFoundError",
    "message": "Project with ID 999 not found",
    "details": null
  }
}
```

### Response - Validation Error (422)
```json
{
  "status": 422,
  "message": "Validation failed",
  "data": null,
  "error": {
    "type": "ValidationError",
    "message": "Invalid request body",
    "details": [
      {
        "field": "scheduled_at",
        "message": "invalid ISO 8601 datetime"
      },
      {
        "field": "duration_minutes",
        "message": "value must be between 0 and 10080"
      }
    ]
  }
}
```

### Frontend Implementation
```javascript
async function createMeeting(projectId, meetingData) {
  const token = localStorage.getItem('access_token');
  
  try {
    const response = await fetch(
      `/api/v3/projects/${projectId}/meetings`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          title: meetingData.title,
          description: meetingData.description || '',
          scheduled_at: meetingData.scheduledAt.toISOString(),
          duration_minutes: meetingData.durationMinutes || null,
          location: meetingData.location || ''
        })
      }
    );
    
    const data = await response.json();
    
    if (response.ok) {
      return { success: true, meeting: data.data };
    } else if (response.status === 404) {
      return { success: false, error: 'Project not found' };
    } else if (response.status === 403) {
      return { success: false, error: 'Permission denied' };
    } else {
      return { success: false, error: data.error.message };
    }
  } catch (error) {
    return { success: false, error: error.message };
  }
}
```

---

## Flow 6: Add Meeting Participant

### Endpoint
```
POST /api/v3/meetings/{meeting_id}/participants
```

### Request Details
```
Method: POST
URL: http://localhost:8000/api/v3/meetings/1/participants
Content-Type: application/json
Authorization: Bearer <token>
Required Permission: MEETINGS_UPDATE
Path Parameter: meeting_id = 1
```

### Request Payload
```json
{
  "user_id": 5
}
```

### Response - Success (201 Created)
```json
{
  "status": 201,
  "message": "Participant added successfully",
  "data": {
    "meeting_id": 1,
    "user_id": 5,
    "user": {
      "id": 5,
      "login": "john.doe",
      "email": "john.doe@example.com",
      "firstName": "John",
      "lastName": "Doe"
    },
    "added_at": "2026-04-13T11:00:00Z"
  },
  "error": null
}
```

### Response - User Already Participant (409 Conflict)
```json
{
  "status": 409,
  "message": "Participant addition failed",
  "data": null,
  "error": {
    "type": "DuplicateError",
    "message": "User is already a participant in this meeting",
    "details": null
  }
}
```

### Response - User Not Found (404 Not Found)
```json
{
  "status": 404,
  "message": "Participant addition failed",
  "data": null,
  "error": {
    "type": "NotFoundError",
    "message": "User with ID 999 not found",
    "details": null
  }
}
```

### Frontend Implementation
```javascript
async function addMeetingParticipant(meetingId, userId) {
  const token = localStorage.getItem('access_token');
  
  try {
    const response = await fetch(
      `/api/v3/meetings/${meetingId}/participants`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ user_id: userId })
      }
    );
    
    const data = await response.json();
    
    if (response.ok) {
      return { success: true, participant: data.data };
    } else if (response.status === 409) {
      return { 
        success: false, 
        error: 'User already participates in this meeting' 
      };
    } else if (response.status === 404) {
      return { success: false, error: 'User or meeting not found' };
    } else {
      return { success: false, error: data.error.message };
    }
  } catch (error) {
    return { success: false, error: error.message };
  }
}
```

---

## Flow 7: Update Meeting

### Endpoint
```
PATCH /api/v3/meetings/{meeting_id}
```

### Request Details
```
Method: PATCH
URL: http://localhost:8000/api/v3/meetings/1
Content-Type: application/json
Authorization: Bearer <token>
Required Permission: MEETINGS_UPDATE
Path Parameter: meeting_id = 1
```

### Request Payload (Only include fields to update)
```json
{
  "title": "Q1 Budget Review - RESCHEDULED",
  "location": "Conference Room B",
  "scheduled_at": "2026-05-16T14:00:00Z"
}
```

### Response - Success (200 OK)
```json
{
  "status": 200,
  "message": "Meeting updated successfully",
  "data": {
    "id": 1,
    "project_id": 1,
    "title": "Q1 Budget Review - RESCHEDULED",
    "description": "Review and finalize Q1 budget allocation across departments",
    "scheduled_at": "2026-05-16T14:00:00Z",
    "duration_minutes": 90,
    "location": "Conference Room B",
    "created_by_id": 1,
    "created_at": "2026-04-13T10:45:30Z",
    "updated_at": "2026-04-13T11:15:00Z"
  },
  "error": null
}
```

### Frontend Implementation
```javascript
async function updateMeeting(meetingId, updates) {
  const token = localStorage.getItem('access_token');
  
  // Only include fields that are defined
  const body = {};
  if (updates.title !== undefined) body.title = updates.title;
  if (updates.description !== undefined) body.description = updates.description;
  if (updates.scheduledAt !== undefined) body.scheduled_at = updates.scheduledAt.toISOString();
  if (updates.durationMinutes !== undefined) body.duration_minutes = updates.durationMinutes;
  if (updates.location !== undefined) body.location = updates.location;
  
  try {
    const response = await fetch(
      `/api/v3/meetings/${meetingId}`,
      {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(body)
      }
    );
    
    const data = await response.json();
    
    if (response.ok) {
      return { success: true, meeting: data.data };
    } else {
      return { success: false, error: data.error.message };
    }
  } catch (error) {
    return { success: false, error: error.message };
  }
}
```

---

## Complete Request Flow Diagram

### User Registration → Login → Create Project → Create Meeting

```
┌─────────────────────────────────────────────────────────────────┐
│ FRONTEND APPLICATION                                            │
└─────────────────────────────────────────────────────────────────┘
                               │
                               │
                    ┌──────────┴──────────┐
                    │                     │
             ┌──────▼──────┐      ┌──────▼──────┐
             │ Login Page  │      │ Dashboard   │
             └──────┬──────┘      └─────────────┘
                    │
           ┌────────┴────────┐
           │ POST /login     │
           │ Enter username  │
           │ Enter password  │
           └────────┬────────┘
                    │
        ┌───────────▼───────────┐
        │ BACKEND - Login Flow  │
        │ ✓ Verify credentials  │
        │ ✓ Hash password check │
        │ ✓ Generate JWT        │
        │ ✓ Set token_exp=15min │
        └───────────┬───────────┘
                    │
           ┌────────▼────────┐
           │ 200 OK          │
           │ access_token ✓  │
           │ refresh_token✓  │
           └────────┬────────┘
                    │
        (Store tokens in localStorage, set auth header)
                    │
           ┌────────▼────────┐
           │ GET /users/me   │
           │ Authorization: │
           │ Bearer <token>  │
           └────────┬────────┘
                    │
        ┌───────────▼───────────────┐
        │ BACKEND - Validate Token  │
        │ ✓ Decode JWT              │
        │ ✓ Check expiration        │
        │ ✓ Get user_id from claims │
        │ ✓ Fetch user from DB      │
        └───────────┬───────────────┘
                    │
           ┌────────▼────────────┐
           │ 200 OK              │
           │ User data (Admin)✓  │
           └────────┬────────────┘
                    │
        (User logged in successfully)
                    │
           ┌────────▼──────────┐
           │ Create Project    │
           │ "Q1 Initiative"   │
           │ POST /projects    │
           └────────┬──────────┘
                    │
        ┌───────────▼───────────────┐
        │ BACKEND - Create Project  │
        │ ✓ Validate project data   │
        │ ✓ Check PROJECTS_CREATE   │
        │ ✓ Insert to DB            │
        │ ✓ Return project_id=1     │
        └───────────┬───────────────┘
                    │
           ┌────────▼────────────┐
           │ 201 Created         │
           │ Project ID=1 ✓      │
           └────────┬────────────┘
                    │
           ┌────────▼──────────────┐
           │ Create Meeting in     │
           │ Project              │
           │ "Budget Review"       │
           │ POST /projects/1/     │
           │   meetings            │
           └────────┬──────────────┘
                    │
        ┌───────────▼───────────────┐
        │ BACKEND - Create Meeting  │
        │ ✓ Validate meeting data   │
        │ ✓ Check MEETINGS_CREATE   │
        │ ✓ Get user_id from token  │
        │ ✓ Insert with created_by  │
        │ ✓ Return meeting_id=1     │
        └───────────┬───────────────┘
                    │
           ┌────────▼────────────┐
           │ 201 Created         │
           │ Meeting ID=1 ✓      │
           └────────┬────────────┘
                    │
        (Meeting created successfully)
                    │
           ┌────────▼──────────────┐
           │ Display Meeting on    │
           │ Dashboard            │
           └──────────────────────┘
```

---

## Error Handling Flow

### Token Expired Scenario

```
REQUEST: GET /api/v3/users/me
HEADER: Authorization: Bearer <expired_token>

RESPONSE: 401 Unauthorized
{
  "error": {
    "type": "AuthenticationError",
    "message": "Token has expired"
  }
}

FRONTEND ACTION:
1. Detect 401 response
2. Retrieve refresh_token from localStorage
3. POST /api/v3/users/login?refresh=true
4. Get new access_token
5. Retry original request
6. If refresh fails, redirect to login page
```

---

## Performance Considerations

### Pagination Example
```javascript
// Good - Paginated requests
const response = await fetch(
  '/api/v3/projects?offset=1&pageSize=20'
);
// Response size: ~5-10 KB

// Bad - Requesting all data at once
const response = await fetch(
  '/api/v3/projects?pageSize=10000'
);
// Response size: Could be >100 MB if many projects
```

### Batch Operations
```javascript
// Instead of:
for (let userId of userIds) {
  await addMeetingParticipant(meetingId, userId);  // N requests
}

// Consider:
const promises = userIds.map(userId =>
  addMeetingParticipant(meetingId, userId)
);
await Promise.all(promises);  // Parallel requests
```

---

**Document Version**: 1.0
**Last Updated**: 2026-04-13
**Test Coverage**: 26/26 endpoints tested ✓
