# PMIS_Python API v3 - Complete Request Lifecycle Documentation

**Version:** 1.0  
**Date:** April 14, 2026  
**Framework:** FastAPI (Python)  
**Database:** SQLite with SQLAlchemy ORM

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Request Flow & Middlewares](#request-flow--middlewares)
3. [Module Endpoints](#module-endpoints)
   - [Users Module](#users-module)
   - [Projects Module](#projects-module)
   - [Project Members Module](#project-members-module)
   - [Roles Module](#roles-module)
   - [Work Packages Module](#work-packages-module)
   - [Work Package Types Module](#work-package-types-module)
   - [Meetings Module](#meetings-module)

---

## Architecture Overview

### Technology Stack

- **Framework:** FastAPI 0.95+
- **Database:** SQLite with SQLAlchemy ORM
- **Authentication:** JWT Bearer tokens
- **Authorization:** Role-Based Access Control (RBAC)
- **Response Format:** HAL+JSON (OpenProject-compatible)

### Application Structure

```
app/
├── main.py                           # FastAPI app initialization
├── api/
│   └── router.py                     # Central router consolidating all v3 endpoints
│   └── v3/                           # API v3 modules
│       ├── users/
│       ├── projects/
│       ├── project_members/
│       ├── roles/
│       ├── work_packages/
│       ├── work_package_types/
│       └── meetings/
├── core/
│   ├── config.py                     # Configuration settings
│   ├── security.py                   # JWT token handling
│   ├── rbac.py                       # Role and permission definitions
│   ├── errors.py                     # Custom exception classes
│   ├── response.py                   # HAL+JSON response formatters
│   ├── base_controller.py            # Base controller utilities
│   ├── dependencies.py               # Dependency injection utilities
│   └── middleware/
│       ├── auth.py                   # JWT authentication middleware
│       ├── logging.py                # Request/response logging
│       └── rbac.py                   # Permission validation middleware
├── domain/                           # Domain models (business logic)
├── infrastructure/
│   └── db/
│       ├── session.py                # Database session management
│       ├── models/                   # SQLAlchemy ORM models
│       └── repositories/             # Data access layer
└── shared/                           # Shared utilities
```

---

## Request Flow & Middlewares

### Complete Request Processing Pipeline

```
1. HTTP Request arrives at FastAPI
                ↓
2. CORS Middleware (CORSMiddleware)
   - Validates cross-origin requests
                ↓
3. Logging Middleware (LoggingMiddleware)
   - Generates unique request ID
   - Logs: {METHOD} {PATH} [{REQUEST_ID}] User: {user_login}
   - Tracks request start time
                ↓
4. Authentication Middleware (AuthenticationMiddleware)
   - Extracts JWT Bearer token from Authorization header
   - Decodes and validates token
   - Attaches to request.state:
     * request.state.user_id (int | None)
     * request.state.user_login (str | None)
     * request.state.user_role (Role enum)
     * request.state.is_admin (bool)
   - For unauthenticated requests: sets role = ANONYMOUS
                ↓
5. Route Matching & Permission Check
   - Routes defined with @router.get(), @router.post(), etc.
   - dependencies=[require_permission(PERMISSION_NAME)]
   - RBAC Middleware checks:
     * Is user authenticated? (role != ANONYMOUS)
     * Does user have required permission?
     * Raises AuthenticationError or AuthorizationError if fails
                ↓
6. FastAPI Dependency Injection
   - get_db() → DatabaseSession
   - Query parameters validated
   - Request body validated against schema
                ↓
7. Controller Execution
   - Receives: Request, data/query, database session
   - Calls business logic services
   - Formats response
                ↓
8. Service Layer Execution
   - Business logic (validation, calculations)
   - Database operations via repositories
   - Returns ServiceResult object
                ↓
9. Database Operations
   - Query/insert/update/delete via SQLAlchemy ORM
   - Table access for persistence
                ↓
10. Response Formatting
    - Converts data to HAL+JSON format
    - Adds _type and _links
    - Wraps in api_response() envelope
                ↓
11. Logging Middleware (response phase)
    - Logs: {METHOD} {PATH} [{REQUEST_ID}] Status: {CODE} Duration: {ms}s
    - Adds X-Request-ID header
                ↓
12. HTTP Response sent to client
```

### Middleware Details

#### 1. CORSMiddleware (Built-in FastAPI)

```python
allow_origins = settings.CORS_ORIGINS
allow_credentials = True
allow_methods = ["*"]
allow_headers = ["*"]
```

#### 2. LoggingMiddleware

**File:** `app/core/middleware/logging.py`

**What it does:**

- Generates unique request UUID
- Logs all incoming requests with method, path, user
- Tracks request duration
- Logs response status and duration
- Adds `X-Request-ID` header to response

**Request State Variables Set:**

- `request.state.request_id` (str)

#### 3. AuthenticationMiddleware

**File:** `app/core/middleware/auth.py`

**What it does:**

1. Extracts Authorization header: `Authorization: Bearer <jwt_token>`
2. Decodes JWT using `decode_access_token(token)`
3. Extracts claims from payload:
   - `user_id` → request.state.user_id
   - `sub` (subject) → request.state.user_login
   - `role` → request.state.user_role
   - `is_admin` → request.state.is_admin

**JWT Token Structure:**

```json
{
  "user_id": 1,
  "sub": "admin", // login field
  "role": "admin", // Role enum value
  "is_admin": true,
  "exp": 1644926400, // expiration timestamp
  "iat": 1644840000 // issued at timestamp
}
```

**Token Expiration:**

- Default: 60 minutes (configurable)
- Uses HS256 algorithm
- Secret key from settings.SECRET_KEY

#### 4. RBAC Middleware (Permission Check)

**File:** `app/core/middleware/rbac.py`

**What it does:**

- Validates required permission via `require_permission(Permission)`
- Checks: 1) User is authenticated, 2) User has permission
- Raises `AuthenticationError` if not authenticated
- Raises `AuthorizationError` if permission denied

**Permission System:**

```python
class Role(str, Enum):
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"
    ANONYMOUS = "anonymous"

# Role → Permissions mapping
ROLE_PERMISSIONS = {
    Role.ADMIN: {...all permissions...},
    Role.MEMBER: {...member permissions...},
    Role.VIEWER: {...viewer read-only...},
    Role.ANONYMOUS: {...none...}
}
```

---

## Module Endpoints

### Users Module

**Files:**

- Routes: `app/api/v3/users/routes.py`
- Controller: `app/api/v3/users/controller.py`
- Schemas: `app/api/v3/users/schemas.py`
- Services: `app/api/v3/users/services/`
- Database Model: `app/infrastructure/db/models/user.py`
- Repository: `app/infrastructure/db/repositories/user_repository.py`

#### Endpoint 1: POST /api/v3/users/login

**Purpose:** Authenticate user and obtain JWT access token

**Request:**

```json
{
  "login": "string",
  "password": "string"
}
```

**Request Schema:** `LoginRequest`

```python
class LoginRequest(BaseModel):
    login: str
    password: str
```

**Permission Required:** None (public endpoint)

**Route Handler:** `routes.py:login()`

**Controller:** `UserController.login(LoginRequest, Session)`

**Service Flow:**

1. `authenticate_user()` → `app/api/v3/users/services/authenticate.py`
2. Query user by login from database
3. Verify password using `verify_password(plain, hashed)`
4. Generate JWT token: `create_access_token({"user_id": ..., "sub": login, "role": ..., "is_admin": ...})`
5. Generate refresh token (optional)
6. Return: `{"access_token": "...", "token_type": "bearer", "user": {...}}`

**Database Tables Involved:**

- **users** (read)
  - Columns: id, login, hashed_password, email, first_name, last_name, admin, status, created_at, updated_at

**Response (HAL+JSON):**

```json
{
  "ok": true,
  "data": {
    "_type": "Login",
    "access_token": "eyJhbGc...",
    "token_type": "bearer",
    "refresh_token": "eyJhbGc...",
    "user": {
      "_type": "User",
      "_links": {
        "self": { "href": "/api/v3/users/1", "title": "admin" }
      },
      "id": 1,
      "login": "admin",
      "firstName": "Admin",
      "lastName": "User",
      "email": "admin@example.com",
      "admin": true,
      "status": "active",
      "createdAt": "2025-01-01T00:00:00",
      "updatedAt": "2025-01-01T00:00:00"
    }
  },
  "message": null,
  "error": null
}
```

**Artifacts Generated:**

- JWT access token (stored client-side)
- Refresh token (stored client-side)
- Session via token (stateless)

---

#### Endpoint 2: POST /api/v3/users/introspect

**Purpose:** Check if token is valid, optionally refresh expired token

**Request:**

```json
{
  "access_token": "string",
  "refresh_token": "string"
}
```

**Request Schema:** `IntrospectRequest`

**Permission Required:** None (public endpoint)

**Route Handler:** `routes.py:introspect()`

**Controller:** `UserController.introspect(IntrospectRequest, Session)`

**Service Flow:**

1. `introspect_tokens()` → `app/api/v3/users/services/introspect.py`
2. If access_token provided:
   - Verify token: `verify_access_token(token)`
   - If valid: return `{"active": true, "user": {...}}`
   - If expired: check if refresh_token provided
3. If refresh_token provided:
   - Verify refresh token
   - Generate new access token
   - Return `{"access_token": "...", "token_type": "bearer", "user": {...}}`

**Database Tables Involved:**

- **users** (read)

**Response Examples:**

_When token is active:_

```json
{
  "ok": true,
  "data": {
    "_type": "Introspect",
    "active": true,
    "user": {...} // User HAL+JSON
  }
}
```

_When token rotates:_

```json
{
  "ok": true,
  "data": {
    "_type": "Introspect",
    "access_token": "...",
    "refresh_token": "...",
    "token_type": "bearer",
    "user": {...}
  }
}
```

---

#### Endpoint 3: GET /api/v3/users/me

**Purpose:** Get current authenticated user's profile

**Query Parameters:** None

**Permission Required:** `None (authenticated users only)`

**Route Handler:** `routes.py:get_me()`

**Middleware Flow:**

1. AuthenticationMiddleware: Extract and validate JWT
2. RBAC Middleware: Check authenticated (implicit)

**Controller:** `UserController.get_me(Request, Session)`

**Service Flow:**

1. Extract user_id from request.state.user_id
2. `get_user_by_id(user_id, requesting_user_id=user_id, is_admin=True)`
3. Return user object

**Database Tables Involved:**

- **users** (read)

**Response:**

```json
{
  "ok": true,
  "data": {
    "_type": "User",
    "_links": {...},
    "id": 1,
    "login": "admin",
    ...
  }
}
```

---

#### Endpoint 4: POST /api/v3/users

**Purpose:** Create new user

**Request Payload:**

```json
{
  "login": "string (3-50 chars)",
  "email": "string (valid email)",
  "password": "string (min 8 chars)",
  "firstName": "string (optional)",
  "lastName": "string (optional)",
  "admin": "boolean (optional, default false)"
}
```

**Request Schema:** `UserCreateRequest`

**Permission Required:** `USERS_CREATE` (members and above)

**Route Handler:** `routes.py:create_user()`

**Middleware Flow:**

1. AuthenticationMiddleware: Validate JWT
2. RBAC Middleware: Check `USERS_CREATE` permission
3. Schema Validation: Pydantic validates UserCreateRequest

**Controller:** `UserController.create(Request, UserCreateRequest, Session)`

**Service Flow:**

1. `create_user(db, login, email, password, first_name, last_name, admin)`
2. Validation:
   - Check login not exists (unique constraint)
   - Check email not exists (unique constraint)
   - Hash password: `hash_password(password)` using Argon2
3. Insert into database
4. Return: User object or error

**Database Tables Involved:**

- **users** (write)
  - INSERT with columns: login, email, hashed_password, first_name, last_name, admin, status ('active'), created_at, updated_at

**Response (201 Created):**

```json
{
  "ok": true,
  "data": {
    "_type": "User",
    "_links": {...},
    "id": 2,
    "login": "newuser",
    "email": "newuser@example.com",
    ...
  }
}
```

**Error Responses:**

- 409 Conflict: Login or email already exists
- 422 Validation Error: Invalid email format or password too short
- 403 Forbidden: User lacks USERS_CREATE permission
- 401 Unauthorized: Not authenticated

---

#### Endpoint 5: GET /api/v3/users

**Purpose:** List all users with pagination

**Query Parameters:**

```
offset: integer (page number, 1-indexed, default=1)
pageSize: integer (items per page, 1-100, default=20)
status: string (optional filter: 'active', 'inactive', etc.)
```

**Permission Required:** `USERS_READ_ALL` (admins only) OR `USERS_READ` (self + members)

**Route Handler:** `routes.py:list_users()`

**Middleware Flow:**

1. AuthenticationMiddleware: Validate JWT
2. RBAC Middleware: Check `USERS_READ_ALL` OR `USERS_READ`
3. Query Validation: Pydantic validates offset, pageSize, status

**Controller:** `UserController.list(Request, UserListQuery, Session)`

**Service Flow:**

1. `list_users(db, page, page_size, status, is_admin)`
2. Build SQLAlchemy query:
   - `SELECT * FROM users`
   - Optional filter: WHERE status = ?
   - Admins see all users, non-admins see limited set
3. Calculate pagination: OFFSET, LIMIT
4. Return: PaginatedResult with items, total, page, page_size

**Database Tables Involved:**

- **users** (read)
  - Query: SELECT with pagination
  - Indexes used: idx_users_status

**Response (HAL+JSON Collection):**

```json
{
  "ok": true,
  "data": {
    "_type": "UserCollection",
    "_links": {
      "self": {"href": "/api/v3/users?offset=1&pageSize=20"},
      "first": {"href": "/api/v3/users?offset=1&pageSize=20"},
      "next": {"href": "/api/v3/users?offset=2&pageSize=20"},
      "last": {"href": "/api/v3/users?offset=5&pageSize=20"}
    },
    "_embedded": {
      "elements": [
        {
          "_type": "User",
          "_links": {...},
          "id": 1,
          "login": "admin",
          ...
        },
        ...
      ]
    },
    "count": 20,
    "total": 95,
    "pageSize": 20,
    "offset": 1
  }
}
```

---

#### Endpoint 6: GET /api/v3/users/{user_id}

**Purpose:** Get single user by ID

**URL Parameters:**

- `user_id` (integer, path parameter)

**Permission Required:** `USERS_READ` (members+) - users can read self, admins read all

**Route Handler:** `routes.py:get_user()`

**Middleware Flow:**

1. AuthenticationMiddleware: Validate JWT
2. RBAC Middleware: Check `USERS_READ` permission
3. Path Validation: user_id must be integer

**Controller:** `UserController.get(Request, user_id, Session)`

**Service Flow:**

1. Extract requesting_user_id and is_admin from request.state
2. `get_user_by_id(db, user_id, requesting_user_id, is_admin)`
3. Query user by primary key
4. Authorization check:
   - Admins can read any user
   - Non-admins can only read themselves
5. Return: User object or 404

**Database Tables Involved:**

- **users** (read)
  - Query: SELECT WHERE id = ?
  - Index: Primary key id

**Response:**

```json
{
  "ok": true,
  "data": {
    "_type": "User",
    "_links": {"self": {"href": "/api/v3/users/1", "title": "admin"}},
    "id": 1,
    "login": "admin",
    ...
  }
}
```

**Error Responses:**

- 404 Not Found: User ID doesn't exist
- 403 Forbidden: Trying to read another user when not admin
- 401 Unauthorized: Not authenticated

---

#### Endpoint 7: PATCH /api/v3/users/{user_id}

**Purpose:** Update user details

**URL Parameters:**

- `user_id` (integer)

**Request Payload (all optional):**

```json
{
  "email": "string",
  "firstName": "string",
  "lastName": "string",
  "admin": "boolean",
  "status": "string"
}
```

**Request Schema:** `UserUpdateRequest`

**Permission Required:** `USERS_UPDATE` (members+) - can update self, admins can update all

**Route Handler:** `routes.py:update_user()`

**Middleware Flow:**

1. AuthenticationMiddleware: Validate JWT
2. RBAC Middleware: Check `USERS_UPDATE` permission
3. Schema Validation: Optional fields validated

**Controller:** `UserController.update(Request, user_id, UserUpdateRequest, Session)`

**Service Flow:**

1. `update_user(db, user_id, email, first_name, last_name, admin, status, requesting_user_id, is_admin)`
2. Authorization: admins can update all, others only themselves
3. Build update dict with provided fields
4. Execute: `UPDATE users SET ... WHERE id = ?`
5. Return: Updated user object

**Database Tables Involved:**

- **users** (read + write)
  - UPDATE: email, first_name, last_name, admin, status, updated_at
  - Constraint: email unique if modified

**Response:**

```json
{
  "ok": true,
  "data": {
    "_type": "User",
    "id": 1,
    "email": "newemail@example.com",
    ...
  }
}
```

**Error Responses:**

- 404 Not Found: User doesn't exist
- 403 Forbidden: Authorization failed
- 422 Validation Error: Invalid email format
- 409 Conflict: Email already in use

---

#### Endpoint 8: PATCH /api/v3/users/{user_id}/password

**Purpose:** Update user password

**URL Parameters:**

- `user_id` (integer)

**Request Payload:**

```json
{
  "password": "string (min 8 chars)"
}
```

**Request Schema:** `UserPasswordUpdateRequest`

**Permission Required:** `USERS_UPDATE` (same as update)

**Route Handler:** `routes.py:update_password()`

**Controller:** `UserController.update_password(Request, user_id, UserPasswordUpdateRequest, Session)`

**Service Flow:**

1. `update_password(db, user_id, new_password, requesting_user_id, is_admin)`
2. Authorization: admins can update all, others only themselves
3. Hash new password
4. UPDATE users SET hashed_password = ?, updated_at = NOW()
5. Return: Success message

**Database Tables Involved:**

- **users** (write)
  - UPDATE: hashed_password, updated_at

**Response:**

```json
{
  "ok": true,
  "data": { "_type": "Success", "message": "Password updated successfully" }
}
```

---

#### Endpoint 9: DELETE /api/v3/users/{user_id}

**Purpose:** Delete user

**URL Parameters:**

- `user_id` (integer)

**Permission Required:** `USERS_DELETE_ALL` (admin only)

**Route Handler:** `routes.py:delete_user()`

**Controller:** `UserController.delete(Request, user_id, Session)`

**Service Flow:**

1. `delete_user(db, user_id)`
2. DELETE FROM users WHERE id = ?
3. Return: Success message or 404

**Database Tables Involved:**

- **users** (delete)
- Cascade: CASCADE DELETE for foreign key relationships

**Response:**

```json
{
  "ok": true,
  "data": { "_type": "Success", "message": "User 1 deleted successfully" }
}
```

---

### Projects Module

**Files:**

- Routes: `app/api/v3/projects/routes.py`
- Controller: `app/api/v3/projects/controller.py`
- Schemas: `app/api/v3/projects/schemas.py`
- Services: `app/api/v3/projects/services/`
- Database Model: `app/infrastructure/db/models/project.py`
- Repository: `app/infrastructure/db/repositories/project_repository.py`

**Database Table: projects**

```sql
CREATE TABLE projects (
  id INTEGER PRIMARY KEY,
  identifier VARCHAR(255) UNIQUE NOT NULL,
  name VARCHAR(255) NOT NULL,
  description TEXT,
  active BOOLEAN DEFAULT true,
  public BOOLEAN DEFAULT false,
  status_explanation TEXT,
  parent_id INTEGER FOREIGN KEY projects(id),
  created_at DATETIME DEFAULT NOW(),
  updated_at DATETIME DEFAULT NOW() ON UPDATE NOW()
);

INDEXES:
- idx_projects_identifier (identifier)
- idx_projects_name (name)
- idx_projects_active (active)
- idx_projects_public (public)
- idx_projects_parent_id (parent_id)
```

#### Endpoint 1: POST /api/v3/projects

**Purpose:** Create new project

**Request Payload:**

```json
{
  "identifier": "string (unique, alphanumeric-dash)",
  "name": "string",
  "description": "string (optional)",
  "active": "boolean (optional, default true)",
  "public": "boolean (optional, default false)"
}
```

**Request Schema:** `ProjectCreateRequest`

**Permission Required:** `PROJECTS_CREATE` (members+)

**Service Flow:**

1. Validate project identifier uniqueness
2. Hash or validate identifier format
3. INSERT INTO projects
4. Return project object

**Response:**

```json
{
  "ok": true,
  "data": {
    "_type": "Project",
    "_links": {"self": {"href": "/api/v3/projects/1"}},
    "id": 1,
    "identifier": "PROJ1",
    "name": "Project One",
    ...
  }
}
```

---

#### Endpoint 2: GET /api/v3/projects

**Purpose:** List all projects with pagination

**Query Parameters:**

```
offset: integer (page, 1-indexed)
pageSize: integer (items per page)
active: boolean (optional filter)
public: boolean (optional filter)
```

**Permission Required:** `PROJECTS_READ` (members+)

**Service Flow:**

1. Build query with optional filters (active, public)
2. Apply pagination
3. Return paginated results

**Response:** Collection HAL+JSON

---

#### Endpoint 3: GET /api/v3/projects/{project_id}

**Purpose:** Get single project

**Permission Required:** `PROJECTS_READ`

**Service Flow:**

1. SELECT FROM projects WHERE id = ?
2. Return project

---

#### Endpoint 4: PATCH /api/v3/projects/{project_id}

**Purpose:** Update project

**Request Payload (optional fields):**

```json
{
  "name": "string",
  "description": "string",
  "active": "boolean",
  "public": "boolean"
}
```

**Request Schema:** `ProjectUpdateRequest`

**Permission Required:** `PROJECTS_UPDATE` (members+)

**Service Flow:**

1. UPDATE projects SET ... WHERE id = ?
2. Return updated project

---

#### Endpoint 5: DELETE /api/v3/projects/{project_id}

**Purpose:** Delete project

**Permission Required:** `PROJECTS_DELETE_ALL` (admin only)

**Service Flow:**

1. DELETE FROM projects WHERE id = ?
2. Cascade deletes:
   - project_memberships associated with project
   - work_packages in project
   - meetings in project

---

### Project Members Module

**Files:**

- Routes: `app/api/v3/project_members/routes.py`
- Controller: `app/api/v3/project_members/controller.py`
- Schemas: `app/api/v3/project_members/schemas.py`
- Services: `app/api/v3/project_members/services/`
- Database Model: `app/infrastructure/db/models/project_member.py`
- Repository: `app/infrastructure/db/repositories/project_member_repository.py`

**Database Table: project_members**

```sql
CREATE TABLE project_members (
  id INTEGER PRIMARY KEY,
  project_id INTEGER NOT NULL FOREIGN KEY projects(id),
  user_id INTEGER NOT NULL FOREIGN KEY users(id),
  role_id INTEGER FOREIGN KEY roles(id),
  created_at DATETIME DEFAULT NOW(),
  updated_at DATETIME DEFAULT NOW()
);

UNIQUE(project_id, user_id)
INDEXES:
- idx_project_id
- idx_user_id
```

#### Endpoint 1: POST /api/v3/projects/{project_id}/memberships

**Purpose:** Add user to project (as member)

**Request Payload:**

```json
{
  "user_id": "integer",
  "role_id": "integer (optional)"
}
```

**Permission Required:** `PROJECT_MEMBERS_ADD`

**Service Flow:**

1. Validate project exists
2. Validate user exists
3. Check user not already member (unique constraint)
4. INSERT INTO project_members
5. Return membership

**Response:**

```json
{
  "ok": true,
  "data": {
    "_type": "ProjectMember",
    "_links": { "self": { "href": "/api/v3/memberships/1" } },
    "id": 1,
    "project_id": 1,
    "user_id": 2,
    "role_id": 2
  }
}
```

---

#### Endpoint 2: GET /api/v3/projects/{project_id}/memberships

**Purpose:** List project members

**Query Parameters:**

```
offset: integer
pageSize: integer
```

**Permission Required:** `PROJECT_MEMBERS_READ`

**Service Flow:**

1. SELECT FROM project_members WHERE project_id = ?
2. Apply pagination
3. Return members

---

#### Endpoint 3: PATCH /api/v3/memberships/{membership_id}

**Purpose:** Update member's role

**Request Payload:**

```json
{
  "role_id": "integer"
}
```

**Permission Required:** `PROJECT_MEMBERS_UPDATE`

**Service Flow:**

1. UPDATE project_members SET role_id = ? WHERE id = ?
2. Return updated membership

---

#### Endpoint 4: DELETE /api/v3/memberships/{membership_id}

**Purpose:** Remove user from project

**Permission Required:** `PROJECT_MEMBERS_DELETE`

**Service Flow:**

1. DELETE FROM project_members WHERE id = ?
2. Return success

---

### Roles Module

**Files:**

- Routes: `app/api/v3/roles/routes.py`
- Controller: `app/api/v3/roles/controller.py`
- Schemas: `app/api/v3/roles/schemas.py`
- Services: `app/api/v3/roles/services/`
- Database Model: `app/infrastructure/db/models/role.py`
- Repository: `app/infrastructure/db/repositories/role_repository.py`

**Database Table: roles**

```sql
CREATE TABLE roles (
  id INTEGER PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  description TEXT,
  permissions TEXT,  -- JSON array of permission strings
  created_at DATETIME DEFAULT NOW(),
  updated_at DATETIME DEFAULT NOW()
);

INDEXES:
- idx_roles_name (name)
```

#### Endpoints

1. **POST /api/v3/roles** - Create role (ROLES_CREATE)
2. **GET /api/v3/roles** - List roles (ROLES_READ)
3. **GET /api/v3/roles/{role_id}** - Get role (ROLES_READ)
4. **PATCH /api/v3/roles/{role_id}** - Update role (ROLES_UPDATE)
5. **DELETE /api/v3/roles/{role_id}** - Delete role (ROLES_DELETE)

---

### Work Packages Module

**Files:**

- Routes: `app/api/v3/work_packages/routes.py`
- Controller: `app/api/v3/work_packages/controller.py`
- Schemas: `app/api/v3/work_packages/schemas.py`
- Services: `app/api/v3/work_packages/services/`
- Database Model: `app/infrastructure/db/models/work_package.py`
- Repository: `app/infrastructure/db/repositories/work_package_repository.py`

**Database Table: work_packages**

```sql
CREATE TABLE work_packages (
  id INTEGER PRIMARY KEY,
  project_id INTEGER NOT NULL FOREIGN KEY projects(id),
  type_id INTEGER FOREIGN KEY work_package_types(id),
  subject VARCHAR(255) NOT NULL,
  description TEXT,
  status VARCHAR(50),  -- 'new', 'in_progress', 'closed', etc.
  priority VARCHAR(50),
  assigned_to_id INTEGER FOREIGN KEY users(id),
  created_by_id INTEGER FOREIGN KEY users(id),
  parent_id INTEGER FOREIGN KEY work_packages(id),
  created_at DATETIME DEFAULT NOW(),
  updated_at DATETIME DEFAULT NOW()
);

INDEXES:
- idx_project_id
- idx_type_id
- idx_status
- idx_assigned_to_id
```

#### Endpoint 1: POST /api/v3/projects/{project_id}/work_packages

**Purpose:** Create work package in project

**Request Payload:**

```json
{
  "subject": "string",
  "description": "string",
  "type_id": "integer",
  "status": "string",
  "priority": "string",
  "assigned_to_id": "integer (optional)"
}
```

**Permission Required:** `WORK_PACKAGES_CREATE`

**Service Flow:**

1. Validate project exists
2. Validate type exists
3. INSERT INTO work_packages
4. Return work package

---

#### Endpoint 2: GET /api/v3/projects/{project_id}/work_packages

**Purpose:** List work packages in project

**Permission Required:** `WORK_PACKAGES_VIEW`

**Service Flow:**

1. SELECT FROM work_packages WHERE project_id = ?
2. Return paginated list

---

#### Endpoint 3: GET /api/v3/work_packages/{work_package_id}

**Purpose:** Get single work package

**Permission Required:** `WORK_PACKAGES_VIEW`

---

#### Endpoint 4: PATCH /api/v3/work_packages/{work_package_id}

**Purpose:** Update work package

**Permission Required:** `WORK_PACKAGES_UPDATE`

---

#### Endpoint 5: DELETE /api/v3/work_packages/{work_package_id}

**Purpose:** Delete work package

**Permission Required:** `WORK_PACKAGES_DELETE`

---

### Work Package Types Module

**Files:**

- Routes: `app/api/v3/work_package_types/routes.py`
- Controller: `app/api/v3/work_package_types/controller.py`
- Schemas: `app/api/v3/work_package_types/schemas.py`
- Services: `app/api/v3/work_package_types/services/`
- Database Model: `app/infrastructure/db/models/work_package_type.py`
- Repository: `app/infrastructure/db/repositories/work_package_type_repository.py`

**Database Table: work_package_types**

```sql
CREATE TABLE work_package_types (
  id INTEGER PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  description TEXT,
  created_at DATETIME DEFAULT NOW(),
  updated_at DATETIME DEFAULT NOW()
);

INDEXES:
- idx_name (name)
```

#### Endpoints

1. **GET /api/v3/work_package_types** - List types (WORK_PACKAGE_TYPES_VIEW)
2. **GET /api/v3/work_package_types/{type_id}** - Get type (WORK_PACKAGE_TYPES_VIEW)
3. **POST /api/v3/work_package_types** - Create type (WORK_PACKAGE_TYPES_MANAGE)
4. **PATCH /api/v3/work_package_types/{type_id}** - Update type (WORK_PACKAGE_TYPES_MANAGE)
5. **DELETE /api/v3/work_package_types/{type_id}** - Delete type (WORK_PACKAGE_TYPES_MANAGE)

---

### Meetings Module

**Files:**

- Routes: `app/api/v3/meetings/routes.py`
- Controller: `app/api/v3/meetings/controller.py`
- Schemas: `app/api/v3/meetings/schemas.py`
- Services: `app/api/v3/meetings/services/`
- Database Models:
  - `app/infrastructure/db/models/meeting.py`
  - `app/infrastructure/db/models/meeting_participant.py`
  - `app/infrastructure/db/models/meeting_agenda_item.py`
- Repositories:
  - `app/infrastructure/db/repositories/meeting_repository.py`
  - `app/infrastructure/db/repositories/meeting_participant_repository.py`
  - `app/infrastructure/db/repositories/meeting_agenda_repository.py`

**Database Tables:**

```sql
CREATE TABLE meetings (
  id INTEGER PRIMARY KEY,
  project_id INTEGER NOT NULL FOREIGN KEY projects(id),
  title VARCHAR(255) NOT NULL,
  description TEXT,
  scheduled_at DATETIME NOT NULL,
  duration_minutes INTEGER,
  location VARCHAR(255),
  created_by_id INTEGER FOREIGN KEY users(id),
  created_at DATETIME DEFAULT NOW(),
  updated_at DATETIME DEFAULT NOW()
);

CREATE TABLE meeting_participants (
  id INTEGER PRIMARY KEY,
  meeting_id INTEGER NOT NULL FOREIGN KEY meetings(id),
  user_id INTEGER NOT NULL FOREIGN KEY users(id),
  created_at DATETIME DEFAULT NOW()
);

CREATE TABLE meeting_agenda_items (
  id INTEGER PRIMARY KEY,
  meeting_id INTEGER NOT NULL FOREIGN KEY meetings(id),
  title VARCHAR(255) NOT NULL,
  description TEXT,
  position INTEGER,
  work_package_id INTEGER FOREIGN KEY work_packages(id),
  created_at DATETIME DEFAULT NOW(),
  updated_at DATETIME DEFAULT NOW()
);

INDEXES:
- meetings: idx_project_id, idx_scheduled_at
- meeting_participants: idx_meeting_id, idx_user_id
- meeting_agenda_items: idx_meeting_id, idx_position
```

#### Endpoint 1: POST /api/v3/projects/{project_id}/meetings

**Purpose:** Create meeting in project

**Request Payload:**

```json
{
  "title": "string (required)",
  "description": "string (optional)",
  "scheduled_at": "datetime (required)",
  "duration_minutes": "integer (optional)",
  "location": "string (optional)"
}
```

**Request Schema:** `MeetingCreateRequest`

**Permission Required:** `MEETINGS_CREATE`

**Service Flow:**

1. Validate project exists
2. INSERT INTO meetings (project_id, title, description, scheduled_at, duration_minutes, location, created_by_id, created_at, updated_at)
3. Return meetings object

**Response:**

```json
{
  "ok": true,
  "data": {
    "_type": "Meeting",
    "_links": { "self": { "href": "/api/v3/meetings/1" } },
    "id": 1,
    "project_id": 1,
    "title": "Q1 Planning",
    "description": "Quarterly planning session",
    "scheduled_at": "2025-03-15T10:00:00Z",
    "duration_minutes": 60,
    "location": "Conference Room A",
    "createdAt": "2025-03-01T09:00:00Z"
  }
}
```

---

#### Endpoint 2: GET /api/v3/projects/{project_id}/meetings

**Purpose:** List meetings in project

**Query Parameters:**

```
offset: integer
limit: integer
```

**Permission Required:** `MEETINGS_VIEW`

**Service Flow:**

1. SELECT FROM meetings WHERE project_id = ?
2. Apply pagination
3. Return meetings

---

#### Endpoint 3: GET /api/v3/meetings/{meeting_id}

**Purpose:** Get meeting details

**Permission Required:** `MEETINGS_VIEW`

**Service Flow:**

1. SELECT FROM meetings WHERE id = ?
2. Return meeting

---

#### Endpoint 4: PATCH /api/v3/meetings/{meeting_id}

**Purpose:** Update meeting

**Request Payload (optional fields):**

```json
{
  "title": "string",
  "description": "string",
  "scheduled_at": "datetime",
  "duration_minutes": "integer",
  "location": "string"
}
```

**Request Schema:** `MeetingUpdateRequest`

**Permission Required:** `MEETINGS_UPDATE`

**Service Flow:**

1. UPDATE meetings SET ... WHERE id = ?
2. Return updated meeting

---

#### Endpoint 5: DELETE /api/v3/meetings/{meeting_id}

**Purpose:** Delete meeting

**Permission Required:** `MEETINGS_DELETE`

**Service Flow:**

1. DELETE FROM meetings WHERE id = ?
2. Cascade deletes:
   - meeting_participants with meeting_id
   - meeting_agenda_items with meeting_id

---

#### Endpoint 6: POST /api/v3/meetings/{meeting_id}/participants

**Purpose:** Add participant to meeting

**Request Payload:**

```json
{
  "user_id": "integer"
}
```

**Request Schema:** `ParticipantAddRequest`

**Permission Required:** `MEETINGS_UPDATE`

**Service Flow:**

1. Validate meeting exists
2. Validate user exists
3. INSERT INTO meeting_participants (meeting_id, user_id)
4. Return participant

**Response:**

```json
{
  "ok": true,
  "data": {
    "_type": "MeetingParticipant",
    "_links": { "self": { "href": "/api/v3/meetings/1/participants/2" } },
    "id": 1,
    "meeting_id": 1,
    "user_id": 2
  }
}
```

---

#### Endpoint 7: GET /api/v3/meetings/{meeting_id}/participants

**Purpose:** List meeting participants

**Permission Required:** `MEETINGS_VIEW`

**Service Flow:**

1. SELECT FROM meeting_participants WHERE meeting_id = ?
2. Join with users table to get user details
3. Return participants

---

#### Endpoint 8: DELETE /api/v3/meetings/{meeting_id}/participants/{user_id}

**Purpose:** Remove participant from meeting

**Permission Required:** `MEETINGS_UPDATE`

**Service Flow:**

1. DELETE FROM meeting_participants WHERE meeting_id = ? AND user_id = ?
2. Return success

---

#### Endpoint 9: POST /api/v3/meetings/{meeting_id}/agenda_items

**Purpose:** Create agenda item for meeting

**Request Payload:**

```json
{
  "title": "string (required)",
  "description": "string (optional)",
  "position": "integer (required)",
  "work_package_id": "integer (optional)"
}
```

**Request Schema:** `AgendaItemCreateRequest`

**Permission Required:** `MEETINGS_UPDATE`

**Service Flow:**

1. Validate meeting exists
2. INSERT INTO meeting_agenda_items (meeting_id, title, description, position, work_package_id)
3. Return agenda item

**Response:**

```json
{
  "ok": true,
  "data": {
    "_type": "MeetingAgendaItem",
    "_links": { "self": { "href": "/api/v3/meetings/1/agenda_items/1" } },
    "id": 1,
    "meeting_id": 1,
    "title": "Review Q4 Results",
    "position": 1
  }
}
```

---

#### Endpoint 10: GET /api/v3/meetings/{meeting_id}/agenda_items

**Purpose:** List agenda items for meeting

**Permission Required:** `MEETINGS_VIEW`

**Service Flow:**

1. SELECT FROM meeting_agenda_items WHERE meeting_id = ?
2. ORDER BY position
3. Return agenda items

---

#### Endpoint 11: GET /api/v3/meetings/agenda_items/{agenda_item_id}

**Purpose:** Get single agenda item

**Permission Required:** `MEETINGS_VIEW`

**Service Flow:**

1. SELECT FROM meeting_agenda_items WHERE id = ?
2. Return agenda item

---

#### Endpoint 12: PATCH /api/v3/meetings/agenda_items/{agenda_item_id}

**Purpose:** Update agenda item

**Request Payload:**

```json
{
  "title": "string",
  "description": "string",
  "position": "integer"
}
```

**Request Schema:** `AgendaItemUpdateRequest`

**Permission Required:** `MEETINGS_UPDATE`

**Service Flow:**

1. UPDATE meeting_agenda_items SET ... WHERE id = ?
2. Return updated agenda item

---

#### Endpoint 13: DELETE /api/v3/meetings/agenda_items/{agenda_item_id}

**Purpose:** Delete agenda item

**Permission Required:** `MEETINGS_DELETE`

**Service Flow:**

1. DELETE FROM meeting_agenda_items WHERE id = ?
2. Return success

---

## Response Format Overview

### Success Response Envelope

```json
{
  "ok": true,
  "data": {
    // HAL+JSON resource
  },
  "message": null,
  "error": null
}
```

### Single Resource (HAL+JSON)

```json
{
  "_type": "ResourceType",
  "_links": {
    "self": {"href": "/api/v3/path/id", "title": "optional"}
  },
  "id": 1,
  "field1": "value1",
  ...
}
```

### Collection Response (HAL+JSON)

```json
{
  "_type": "ResourceTypeCollection",
  "_links": {
    "self": {"href": "/api/v3/path?offset=1&pageSize=20"},
    "first": {"href": "/api/v3/path?offset=1&pageSize=20"},
    "next": {"href": "/api/v3/path?offset=2&pageSize=20"},
    "last": {"href": "/api/v3/path?offset=5&pageSize=20"}
  },
  "_embedded": {
    "elements": [
      {resource1},
      {resource2},
      ...
    ]
  },
  "count": 20,
  "total": 95,
  "pageSize": 20,
  "offset": 1
}
```

### Error Response

```json
{
  "ok": false,
  "data": null,
  "message": null,
  "error": {
    "type": "ErrorType",
    "message": "Human readable message",
    "details": {...}
  }
}
```

---

## Key Architectural Patterns

### Service Result Pattern

All service functions return `ServiceResult` objects:

```python
class ServiceResult:
    def __init__(self, data=None, is_success=True, error=None, error_type=None, details=None):
        self.data = data
        self._is_success = is_success
        self.error = error
        self.error_type = error_type
        self.details = details

    def is_success(self) -> bool:
        return self._is_success
```

### Hat-Check Request State

User information attached by middleware:

- `request.state.user_id` (int | None)
- `request.state.user_login` (str | None)
- `request.state.user_role` (Role enum)
- `request.state.is_admin` (bool)
- `request.state.request_id` (str UUID)

### Database Session Lifecycle

- One session per request (dependency injection)
- Automatically committed/rolled back per request
- No multi-request sessions

### Permission Decorators

```python
@router.post("/", dependencies=[require_permission(PERMISSION_NAME)])
def endpoint(request: Request, data: Schema, db: Session):
    ...
```

---

## Error Handling

### HTTP Status Codes Used

- **200 OK**: Successful GET, PATCH
- **201 Created**: Successful POST
- **204 No Content**: DELETE (in some cases)
- **400 Bad Request**: Malformed request
- **401 Unauthorized**: Not authenticated / Token expired
- **403 Forbidden**: Authenticated but lacks permission
- **404 Not Found**: Resource doesn't exist
- **409 Conflict**: Duplicate key / Business logic violation
- **422 Unprocessable Entity**: Validation error
- **500 Internal Server Error**: Unhandled exception

### Exception Handling Pipeline

```
Request
  ↓
[Middleware Processing]
  ↓
[Route Handler]
  → Calls Service
    → Database Operation
      → SQLAlchemy raises exception
        → Caught by exception handler in main.py
          → Converted to HTTP error response
  ↓
Response with error envelope
```

---

## Summary Tables

### All Permissions by Module

| Permission                | Role Level | Purpose                  |
| ------------------------- | ---------- | ------------------------ |
| USERS_CREATE              | MEMBER+    | Create new user          |
| USERS_READ                | MEMBER+    | Read own user            |
| USERS_READ_ALL            | ADMIN      | Read any user            |
| USERS_UPDATE              | MEMBER+    | Update own user          |
| USERS_UPDATE_ALL          | ADMIN      | Update any user          |
| USERS_DELETE_ALL          | ADMIN      | Delete any user          |
| PROJECTS_CREATE           | MEMBER+    | Create project           |
| PROJECTS_READ             | MEMBER+    | Read projects            |
| PROJECTS_UPDATE           | MEMBER+    | Update project           |
| PROJECTS_DELETE_ALL       | ADMIN      | Delete project           |
| PROJECT_MEMBERS_READ      | MEMBER+    | Read project members     |
| PROJECT_MEMBERS_ADD       | MEMBER+    | Add user to project      |
| PROJECT_MEMBERS_UPDATE    | MEMBER+    | Update member role       |
| PROJECT_MEMBERS_DELETE    | MEMBER+    | Remove user from project |
| ROLES_READ                | MEMBER+    | Read roles               |
| ROLES_CREATE              | ADMIN      | Create role              |
| ROLES_UPDATE              | ADMIN      | Update role              |
| ROLES_DELETE              | ADMIN      | Delete role              |
| WORK_PACKAGES_VIEW        | MEMBER+    | View work packages       |
| WORK_PACKAGES_CREATE      | MEMBER+    | Create work package      |
| WORK_PACKAGES_UPDATE      | MEMBER+    | Update work package      |
| WORK_PACKAGES_DELETE      | MEMBER+    | Delete work package      |
| WORK_PACKAGE_TYPES_VIEW   | MEMBER+    | View types               |
| WORK_PACKAGE_TYPES_MANAGE | ADMIN      | Manage types             |
| MEETINGS_VIEW             | MEMBER+    | View meetings            |
| MEETINGS_CREATE           | MEMBER+    | Create meeting           |
| MEETINGS_UPDATE           | MEMBER+    | Update meeting           |
| MEETINGS_DELETE           | MEMBER+    | Delete meeting           |

### Database Tables Summary

| Table                | Purpose                   | Key Columns                              | Relationships                                |
| -------------------- | ------------------------- | ---------------------------------------- | -------------------------------------------- |
| users                | User accounts             | id, login, email, password_hash          | Many-to-Many projects via project_members    |
| projects             | Project definitions       | id, identifier, name, active, public     | One-to-Many members, work_packages, meetings |
| project_members      | User-Project associations | id, project_id, user_id, role_id         | FK: users, projects, roles                   |
| roles                | Predefined roles          | id, name, permissions_json               | One-to-Many project_members                  |
| work_packages        | Tasks/Issues              | id, project_id, type_id, subject, status | FK: projects, work_package_types, users      |
| work_package_types   | Package type definitions  | id, name                                 | One-to-Many work_packages                    |
| meetings             | Meetings/Events           | id, project_id, scheduled_at, title      | One-to-Many participants, agenda_items       |
| meeting_participants | Meeting attendees         | id, meeting_id, user_id                  | FK: meetings, users                          |
| meeting_agenda_items | Meeting agenda items      | id, meeting_id, title, position          | FK: meetings, work_packages                  |

---

## Conclusion

This document provides a complete trace of every request through the PMIS_Python API v3, covering:

- **Request Entry**: How requests are routed and authenticated
- **Middleware Processing**: JWT validation, RBAC permission checks, logging
- **Business Logic**: Controllers and services processing the request
- **Data Persistence**: Which database tables are read/written
- **Response Format**: HAL+JSON structured responses
- **Error Handling**: Exception translation to HTTP responses

All 38+ endpoints across 7 modules follow this consistent pattern, making the API predictable and maintainable.
