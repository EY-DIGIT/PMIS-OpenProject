# PMIS Python - Architecture and API Reference

**Project**: PMIS (Project Management Information System) - FastAPI Backend
**Version**: 3.0.0
**Status**: Production Ready

---

## 1. Technology Stack

| Component | Technology |
|-----------|-----------|
| Framework | FastAPI 0.135.3 |
| Database | SQLite (dev) / PostgreSQL (production) |
| ORM | SQLAlchemy 2.0.49 |
| Authentication | JWT with HS256 |
| Password Hashing | Argon2id |
| Validation | Pydantic 2.12.5 |
| API Format | HAL+JSON (OpenProject compatible) |
| Python Version | 3.12 |
| Server | Uvicorn |

---

## 2. Architecture Overview

### Layered Architecture with DDD

```
┌─────────────────────────────────────────┐
│ API Layer (routes, controllers, schemas)│
├─────────────────────────────────────────┤
│ Service Layer (business logic)          │
├─────────────────────────────────────────┤
│ Domain Layer (domain models/entities)   │
├─────────────────────────────────────────┤
│ Infrastructure (repositories, DB, ORM)  │
├─────────────────────────────────────────┤
│ Core (security, RBAC, errors, config)   │
└─────────────────────────────────────────┘
```

### Architectural Principles

1. **Separation of Concerns**: Each layer has specific responsibilities.
2. **No Circular Dependencies**: Unidirectional dependency flow.
3. **Domain Layer**: Pure business entities, no framework dependencies.
4. **Repository Layer**: All DB access through repos, returns domain models.
5. **Service Layer**: Business logic, returns `ServiceResult<T>`, no HTTP/auth concerns.
6. **Controller Layer**: Request orchestration only, no business logic.
7. **Route Layer**: Route definitions, permission enforcement only.
8. **RBAC Strategy**: Route-level enforcement via `require_permission()` dependency.
9. **Response Format**: Centralized HAL+JSON formatting via `core/response.py`.

### Directory Structure

```
app/
├── main.py                          # Application entry point
├── core/                            # Core functionality
│   ├── config.py                    # Configuration (Pydantic BaseSettings)
│   ├── security.py                  # JWT & password hashing
│   ├── rbac.py                      # Roles & permissions
│   ├── response.py                  # HAL+JSON formatter
│   ├── errors.py                    # Error definitions
│   ├── base_controller.py           # Base controller utilities
│   ├── dependencies.py              # DI helpers
│   └── middleware/
│       ├── auth.py                  # Authentication middleware
│       ├── rbac.py                  # Authorization dependencies
│       └── logging.py              # Logging middleware
├── api/
│   ├── router.py                    # Central API router
│   └── v3/
│       ├── users/                   # User management module
│       ├── projects/                # Project management module
│       ├── project_members/         # Project membership module
│       ├── roles/                   # Role management module
│       ├── work_packages/           # Work packages module
│       ├── work_package_types/      # Work package types module
│       └── meetings/                # Meeting management module
├── domain/                          # Domain models (pure business entities)
│   ├── users/user.py
│   ├── projects/project.py
│   ├── project_members/membership.py
│   ├── roles/role.py
│   ├── work_packages/work_package.py
│   ├── work_package_types/work_package_type.py
│   └── meetings/ (meeting.py, participant.py, agenda_item.py)
├── infrastructure/db/               # Database layer
│   ├── session.py                   # Database session & init
│   ├── models/                      # SQLAlchemy ORM models (10)
│   └── repositories/               # Data access repositories (10)
└── shared/                          # Shared utilities
    ├── service_result.py            # ServiceResult wrapper
    ├── pagination.py                # Pagination utilities
    ├── utils.py                     # Validation helpers
    └── datetime.py                  # DateTime utilities
```

### Request Processing Pipeline

```
 1. HTTP Request → FastAPI
 2. CORS Middleware → validates cross-origin
 3. Logging Middleware → generates request ID, logs request
 4. Authentication Middleware → extracts JWT, sets request.state
    (user_id, user_login, user_role, is_admin)
 5. Route Matching & Permission Check → require_permission() validates RBAC
 6. FastAPI Dependency Injection → get_db(), schema validation
 7. Controller → calls services, formats response
 8. Service Layer → business logic via repositories, returns ServiceResult
 9. Database Operations → SQLAlchemy ORM
10. Response Formatting → HAL+JSON via core/response.py
11. Logging Middleware (response) → logs status, duration, adds X-Request-ID
12. HTTP Response
```

### Key Design Patterns

- **ServiceResult Pattern**: All services return `ServiceResult.ok(data)` or `ServiceResult.fail(error)`.
- **Repository Pattern**: Data access abstraction between service and ORM layers.
- **HAL+JSON Responses**: OpenProject v3 API compatible format with `_type`, `_links`, `_embedded`.
- **RBAC**: Role-based with 4 roles (ADMIN, MEMBER, VIEWER, ANONYMOUS) and 30+ permissions.

---

## 3. Database Schema

### Users

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    login VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    admin BOOLEAN DEFAULT FALSE,
    status VARCHAR(50) DEFAULT 'active',
    refresh_token_jti VARCHAR(255),
    refresh_token_expires_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Projects

```sql
CREATE TABLE projects (
    id INTEGER PRIMARY KEY,
    identifier VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    active BOOLEAN DEFAULT TRUE,
    public BOOLEAN DEFAULT FALSE,
    status_explanation TEXT,
    parent_id INTEGER REFERENCES projects(id),
    status VARCHAR(50) DEFAULT 'new',
    owner VARCHAR(255),
    category VARCHAR(50),
    start_date DATETIME,
    end_date DATETIME,
    created_at DATETIME,
    updated_at DATETIME
);
```

#### Enhanced Project Fields

| Field | Type | Validation | Notes |
|-------|------|-----------|-------|
| status | String | Enum: `new`, `in_progress`, `completed`, `on_hold` | Default: `"new"` |
| owner | String | Username must exist in users table | Optional |
| category | String | Enum: `MSAP`, `MSIP`, `BSP` | Optional |
| start_date | DateTime | Must be future, ISO 8601 | Optional |
| end_date | DateTime | Must be future AND after start_date | Optional |

To modify allowed values, edit `app/api/v3/projects/schemas.py` (`PROJECT_STATUS_CHOICES`, `PROJECT_CATEGORY_CHOICES`).

### Roles

```sql
CREATE TABLE roles (
    id INTEGER PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    permissions JSON,
    builtin BOOLEAN DEFAULT FALSE,
    created_at DATETIME,
    updated_at DATETIME
);
```

### Project Members

```sql
CREATE TABLE project_members (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    roles JSON,
    created_at DATETIME,
    updated_at DATETIME,
    UNIQUE(project_id, user_id)
);
```

### Work Packages

```sql
CREATE TABLE work_packages (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    type_id INTEGER REFERENCES work_package_types(id),
    subject VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(50) DEFAULT 'new',
    priority VARCHAR(50) DEFAULT 'normal',
    done_ratio INTEGER DEFAULT 0,
    assignee_id INTEGER REFERENCES users(id),
    parent_id INTEGER REFERENCES work_packages(id),
    created_at DATETIME,
    updated_at DATETIME
);
```

Domain model values:
- **Status**: `new`, `in_progress`, `resolved`, `closed`, `on_hold`
- **Priority**: `low`, `normal`, `high`, `urgent`
- **Done ratio**: 0-100 integer
- Helper methods: `is_subtask()`, `is_completed()`, `to_dict()`

Services use dependency-injected repositories for cross-entity validation: `ProjectRepository` validates project existence, `ProjectMemberRepository` validates assignee membership, and `WorkPackageRepository` handles work package CRUD.

### Work Package Types

```sql
CREATE TABLE work_package_types (
    id INTEGER PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    internal_name VARCHAR(255) UNIQUE,
    is_builtin BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    position INTEGER,
    created_at DATETIME,
    updated_at DATETIME
);
```

Built-in types: Task, Bug, Feature, Story, Milestone.

### Meetings

```sql
CREATE TABLE meetings (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    scheduled_at DATETIME NOT NULL,
    duration_minutes INTEGER,
    location VARCHAR(255),
    created_by_id INTEGER REFERENCES users(id),
    created_at DATETIME,
    updated_at DATETIME
);
```

### Meeting Participants

```sql
CREATE TABLE meeting_participants (
    id INTEGER PRIMARY KEY,
    meeting_id INTEGER NOT NULL REFERENCES meetings(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    created_at DATETIME,
    UNIQUE(meeting_id, user_id)
);
```

### Meeting Agenda Items

```sql
CREATE TABLE meeting_agenda_items (
    id INTEGER PRIMARY KEY,
    meeting_id INTEGER NOT NULL REFERENCES meetings(id),
    project_id INTEGER NOT NULL REFERENCES projects(id),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    position INTEGER NOT NULL,
    work_package_id INTEGER,
    created_at DATETIME,
    updated_at DATETIME
);
```

---

## 4. API Endpoint Reference

### System Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | No | Root endpoint with API links |
| GET | `/health` | No | Health check |

### User Endpoints (9)

| Method | Path | Permission | Description |
|--------|------|-----------|-------------|
| POST | `/api/v3/users/login` | Public | Authenticate, get JWT token |
| POST | `/api/v3/users/introspect` | Public | Token introspection/refresh |
| GET | `/api/v3/users/me` | Authenticated | Get current user |
| POST | `/api/v3/users` | USERS_CREATE | Create user |
| GET | `/api/v3/users` | USERS_READ_ALL | List users (paginated) |
| GET | `/api/v3/users/{id}` | USERS_READ | Get user by ID |
| PATCH | `/api/v3/users/{id}` | USERS_UPDATE | Update user |
| PATCH | `/api/v3/users/{id}/password` | USERS_UPDATE | Update password |
| DELETE | `/api/v3/users/{id}` | USERS_DELETE_ALL | Delete user |

### Project Endpoints (5)

| Method | Path | Permission | Description |
|--------|------|-----------|-------------|
| POST | `/api/v3/projects` | PROJECTS_CREATE | Create project |
| GET | `/api/v3/projects` | PROJECTS_READ | List projects (filterable) |
| GET | `/api/v3/projects/{id}` | PROJECTS_READ | Get project |
| PATCH | `/api/v3/projects/{id}` | PROJECTS_UPDATE | Update project |
| DELETE | `/api/v3/projects/{id}` | PROJECTS_DELETE_ALL | Delete project |

Query parameters for list: `offset`, `pageSize`, `active` (bool), `public` (bool).

### Project Member Endpoints (4)

| Method | Path | Permission | Description |
|--------|------|-----------|-------------|
| POST | `/api/v3/projects/{project_id}/members` | PROJECT_MEMBERS_ADD | Add member |
| GET | `/api/v3/projects/{project_id}/members` | PROJECT_MEMBERS_READ | List members |
| PATCH | `/api/v3/projects/{project_id}/members/{id}` | PROJECT_MEMBERS_UPDATE | Update member |
| DELETE | `/api/v3/projects/{project_id}/members/{id}` | PROJECT_MEMBERS_DELETE | Remove member |

### Role Endpoints (5)

| Method | Path | Permission | Description |
|--------|------|-----------|-------------|
| POST | `/api/v3/roles` | ROLES_CREATE | Create role |
| GET | `/api/v3/roles` | ROLES_READ | List roles |
| GET | `/api/v3/roles/{id}` | ROLES_READ | Get role |
| PATCH | `/api/v3/roles/{id}` | ROLES_UPDATE | Update role |
| DELETE | `/api/v3/roles/{id}` | ROLES_DELETE | Delete role |

### Work Package Endpoints (5)

| Method | Path | Permission | Description |
|--------|------|-----------|-------------|
| POST | `/api/v3/projects/{project_id}/work_packages` | WORK_PACKAGES_CREATE | Create work package |
| GET | `/api/v3/projects/{project_id}/work_packages` | WORK_PACKAGES_VIEW | List work packages |
| GET | `/api/v3/work_packages/{id}` | WORK_PACKAGES_VIEW | Get work package |
| PATCH | `/api/v3/work_packages/{id}` | WORK_PACKAGES_UPDATE | Update work package |
| DELETE | `/api/v3/work_packages/{id}` | WORK_PACKAGES_DELETE | Delete work package |

### Work Package Type Endpoints (5)

| Method | Path | Permission | Description |
|--------|------|-----------|-------------|
| GET | `/api/v3/work_package_types` | WORK_PACKAGE_TYPES_VIEW | List types |
| POST | `/api/v3/work_package_types` | WORK_PACKAGE_TYPES_MANAGE | Create type |
| GET | `/api/v3/work_package_types/{id}` | WORK_PACKAGE_TYPES_VIEW | Get type |
| PATCH | `/api/v3/work_package_types/{id}` | WORK_PACKAGE_TYPES_MANAGE | Update type |
| DELETE | `/api/v3/work_package_types/{id}` | WORK_PACKAGE_TYPES_MANAGE | Delete type |

### Meeting Endpoints (12)

| Method | Path | Permission | Description |
|--------|------|-----------|-------------|
| POST | `/api/v3/projects/{project_id}/meetings` | MEETINGS_CREATE | Create meeting |
| GET | `/api/v3/projects/{project_id}/meetings` | MEETINGS_VIEW | List meetings |
| GET | `/api/v3/meetings/{id}` | MEETINGS_VIEW | Get meeting |
| PATCH | `/api/v3/meetings/{id}` | MEETINGS_UPDATE | Update meeting |
| DELETE | `/api/v3/meetings/{id}` | MEETINGS_DELETE | Delete meeting |
| POST | `/api/v3/meetings/{id}/participants` | MEETINGS_UPDATE | Add participant |
| GET | `/api/v3/meetings/{id}/participants` | MEETINGS_VIEW | List participants |
| DELETE | `/api/v3/meetings/{id}/participants/{uid}` | MEETINGS_UPDATE | Remove participant |
| POST | `/api/v3/meetings/{id}/agenda_items` | MEETINGS_UPDATE | Create agenda item |
| GET | `/api/v3/meetings/{id}/agenda_items` | MEETINGS_VIEW | List agenda items |
| PATCH | `/api/v3/meetings/{id}/agenda_items/{item_id}` | MEETINGS_UPDATE | Update agenda item |
| DELETE | `/api/v3/meetings/{id}/agenda_items/{item_id}` | MEETINGS_DELETE | Delete agenda item |

---

## 5. Response Format (HAL+JSON)

### Single Resource

```json
{
  "data": {
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
    "createdAt": "2025-12-15T11:26:26.833674",
    "updatedAt": "2025-12-15T11:26:26.833674"
  },
  "message": null,
  "error": null,
  "status": 200
}
```

### Collection

```json
{
  "data": {
    "_type": "Collection",
    "_links": {
      "self": {"href": "/api/v3/users?offset=1&pageSize=10"},
      "first": {"href": "/api/v3/users?offset=1&pageSize=10"},
      "next": {"href": "/api/v3/users?offset=2&pageSize=10"},
      "last": {"href": "/api/v3/users?offset=5&pageSize=10"}
    },
    "total": 50,
    "count": 10,
    "pageSize": 10,
    "offset": 1,
    "_embedded": {
      "elements": [...]
    }
  }
}
```

### Error

```json
{
  "data": null,
  "error": {
    "_type": "Error",
    "errorIdentifier": "not_found",
    "message": "User with ID 99 not found"
  },
  "status": 404
}
```

### HTTP Status Codes

| Status | Usage |
|--------|-------|
| 200 | Successful GET, PATCH |
| 201 | Successful POST (create) |
| 204 | Successful DELETE |
| 400 | Bad request |
| 401 | Unauthorized (missing/invalid token) |
| 403 | Forbidden (insufficient permissions) |
| 404 | Resource not found |
| 409 | Conflict (duplicate) |
| 422 | Validation error |
| 500 | Server error |

---

## 6. RBAC Permissions

### Roles

- **ADMIN** - Full system access
- **MEMBER** - Create, read, update most resources
- **VIEWER** - Read-only access
- **ANONYMOUS** - No access (unauthenticated)

### Permission Matrix

| Permission | Admin | Member | Viewer |
|-----------|-------|--------|--------|
| USERS_CREATE | Y | Y | |
| USERS_READ | Y | Y | Y |
| USERS_READ_ALL | Y | | |
| USERS_UPDATE | Y | Y (self) | |
| USERS_DELETE_ALL | Y | | |
| PROJECTS_CREATE | Y | Y | |
| PROJECTS_READ | Y | Y | Y |
| PROJECTS_UPDATE | Y | Y | |
| PROJECTS_DELETE_ALL | Y | | |
| PROJECT_MEMBERS_* | Y | Y | Read only |
| ROLES_READ | Y | Y | |
| ROLES_CREATE/UPDATE/DELETE | Y | | |
| WORK_PACKAGES_VIEW | Y | Y | Y |
| WORK_PACKAGES_CREATE/UPDATE/DELETE | Y | Y | |
| WORK_PACKAGE_TYPES_VIEW | Y | Y | |
| WORK_PACKAGE_TYPES_MANAGE | Y | | |
| MEETINGS_VIEW | Y | Y | Y |
| MEETINGS_CREATE/UPDATE/DELETE | Y | Y | |

---

## 7. Configuration

### Environment Variables

```bash
SECRET_KEY=<32+ character secure key>
DATABASE_URL=sqlite:///./pmis.db  # or postgresql://...
DEBUG=False
CORS_ORIGINS=["http://localhost:3000"]
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
DEFAULT_PAGE_SIZE=20
MAX_PAGE_SIZE=100
```

### Default Admin Credentials

```
Login: admin
Password: admin123
Email: admin@example.com
```

### Running the Application

```bash
# Development
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Production
gunicorn -w 4 -b 0.0.0.0:8000 --worker-class uvicorn.workers.UvicornWorker app.main:app
```

### API Documentation URLs

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI JSON: `http://localhost:8000/openapi.json`
