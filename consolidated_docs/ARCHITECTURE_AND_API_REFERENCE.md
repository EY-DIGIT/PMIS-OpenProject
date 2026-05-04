# PMIS Python — Architecture and API Reference

**Project**: PMIS (Project Management Information System) — FastAPI backend
**Version**: 3.0.0
**Status**: Production-ready
**Last refresh**: 2026-05-04 (after doc 24)

---

## 1. Technology Stack

| Component | Technology |
|-----------|-----------|
| Framework | FastAPI 0.135.3 |
| Database | SQLite (dev/tests) / PostgreSQL 16 (production) |
| ORM | SQLAlchemy 2.0.49 |
| Migrations | Alembic (auto-run on boot for non-SQLite engines) |
| Authentication | JWT HS256, Argon2id password hashing |
| Validation | Pydantic 2.12.5 |
| API Format | HAL+JSON envelope (OpenProject v3 compatible) |
| Python | 3.12 |
| Server | Uvicorn (dev) / Gunicorn + Uvicorn workers (prod) |

---

## 2. Architecture Overview

### Layered Architecture (DDD-flavored)

```
┌─────────────────────────────────────────────────────────────┐
│ API Layer (routes, controllers, schemas)                    │
├─────────────────────────────────────────────────────────────┤
│ Service Layer (business logic, returns ServiceResult<T>)    │
├─────────────────────────────────────────────────────────────┤
│ Domain Layer (pure business entities — no framework deps)   │
├─────────────────────────────────────────────────────────────┤
│ Infrastructure (repositories, SQLAlchemy ORM, DB session)   │
├─────────────────────────────────────────────────────────────┤
│ Core (security, RBAC middleware, config, errors, response)  │
└─────────────────────────────────────────────────────────────┘
```

### Architectural Principles

1. **Separation of concerns** — each layer has a single responsibility.
2. **Unidirectional dependencies** — no circular imports.
3. **Domain layer is framework-free** — pure dataclasses.
4. **Repository pattern** — all DB access through repos; repos return domain entities.
5. **Service layer** — business logic, returns `ServiceResult<T>`; no HTTP / RBAC concerns.
6. **Controller layer** — HAL+JSON projection only; no business logic.
7. **Route layer** — declares URL + permission code only.
8. **RBAC** — string-coded `require_permission("…")` dependency, hydrated per-request from the DB.
9. **Response format** — centralized HAL+JSON envelope via `core/response.py` and `core/base_controller.py`.

### Directory Structure (current state)

```
app/
├── main.py                            # Application entry point
├── core/
│   ├── config.py                      # Settings (Pydantic BaseSettings)
│   ├── security.py                    # JWT + Argon2 password hashing
│   ├── rbac.py                        # Legacy enums kept for back-compat
│   ├── permissions.py                 # Canonical permission code registry (doc 21B)
│   ├── response.py                    # HAL+JSON formatters
│   ├── base_controller.py             # ok / created / no_content / error / stamp_deprecation
│   ├── errors.py                      # NotFoundError, ValidationError, AuthorizationError, …
│   ├── dependencies.py                # FastAPI DI helpers
│   ├── project_lock.py                # Baseline-vs-version writability guards
│   └── middleware/
│       ├── auth.py                    # JWT decode + per-request perm hydration (doc 21B)
│       ├── rbac.py                    # require_permission(string code) dependency
│       └── logging.py                 # X-Request-ID + duration logging
├── api/
│   ├── router.py                      # Central router; mounts every v3 module
│   └── v3/
│       ├── users/                     # Users + RBAC user-side assignments
│       ├── projects/                  # Projects (incl. versions, audit, baseline_version_sync)
│       ├── project_members/
│       ├── roles/                     # Legacy /roles + /roles/{id}/permissions (deprecated → /master/roles)
│       ├── permissions/               # Legacy /permissions catalog (deprecated → /master/permissions)
│       ├── master_data/               # Consolidated /api/v3/master/* router (doc 20 + 21B follow-up)
│       ├── milestones/                # M layer — depends_on edges (doc 21A)
│       ├── activities/                # A layer
│       ├── tasks/                     # T layer (version-only)
│       ├── subtasks/                  # S layer (version-only; nested per doc 24)
│       ├── tree/                      # GET /projects/{id}/tree — full nested response
│       ├── catalogs/                  # Legacy GETs (deprecated → /master)
│       ├── vendors/                   # Legacy CRUD (deprecated → /master/vendors)
│       ├── resource_types/            # Legacy GETs (deprecated → /master/resource_types)
│       ├── work_packages/             # Reserved; not part of doc-19+ flow
│       ├── work_package_types/        # Reserved; not part of doc-19+ flow
│       ├── meetings/
│       ├── comments/                  # Polymorphic comments on M/A/T/S
│       └── attachments/               # File uploads tied to M/A/T/S
├── domain/                            # Pure business entities
├── infrastructure/db/
│   ├── session.py                     # Engine, sessionmaker, init_db, drift healers
│   ├── models/                        # 34 SQLAlchemy models
│   └── repositories/                  # Per-aggregate data access
└── shared/
    ├── service_result.py              # ServiceResult<T>
    ├── pagination.py                  # 1-indexed page helpers
    ├── labels.py                      # M/A/T/S display labels (doc 22, doc 24)
    ├── position_heal.py               # Self-heal duplicate live positions (doc 22 hotfix)
    ├── date_rules.py                  # validate_entity_dates / validate_resource_dates
    ├── upsert_helpers.py
    ├── project_code.py                # Project-code generator
    └── utils.py
```

### Request Processing Pipeline

```
 1. HTTP Request → FastAPI
 2. CORS Middleware
 3. Logging Middleware  → assigns X-Request-ID, logs request
 4. Authentication Middleware (doc 21B)
       - decodes JWT (HS256)
       - checks revoked-token blacklist by jti
       - on success, sets request.state:
            user_id, user_login, token_jti, token_exp
            user_permissions: Set[str]   ← from RbacRepository (one DB query)
            is_admin: bool                ← from membership in seeded `admin` role
 5. Route → Permission check via require_permission("module:action")
       - reads request.state.user_permissions
       - 401 if user_id is None, 403 if code not in the set
 6. FastAPI dependency injection (get_db, schema validation)
 7. Controller → calls services, formats HAL+JSON response
 8. Service → business logic via repositories, returns ServiceResult
 9. Repository → SQLAlchemy ORM
10. Response Formatting → HAL+JSON via core/response.py
11. Logging Middleware (response) → status + duration + X-Request-ID
12. HTTP Response
```

### Key Design Patterns

- **ServiceResult** — `ServiceResult.ok(data)` / `ServiceResult.fail(error, error_type, details)`. Controllers map `error_type` to HTTP status.
- **Repository pattern** — all DB access through repos; repos own SQL and return domain entities.
- **HAL+JSON envelope** — every response is `{ "data": { _type, _links, _embedded?, … }, "status": <int> }` or `{ "error": { errorIdentifier, message, … }, "status": <int> }`.
- **String-coded RBAC** — routes call `require_permission("projects:create")`. The string is the canonical code (see [app/core/permissions.py](../app/core/permissions.py)). Codes are upserted into the DB at boot.
- **Soft-delete everywhere** — `deleted_at` + (where present) `deleted_by`. Reads filter by `deleted_at IS NULL` unless `include_deleted=True`. Restore endpoints (`POST /…/restore`) clear `deleted_at`.
- **Version-only entities** — tasks and subtasks live exclusively on version projects (`is_version=true`). Milestones and activities live on baselines and propagate to active versions.

---

## 3. Database Schema

The full schema (every table, column, index, constraint, FK relationship) is documented in **[DATABASE_SCHEMA.md](./DATABASE_SCHEMA.md)**.

Auto-generated DDL for both dialects lives in [scripts/ddl/](../scripts/ddl/) — regenerate with `python scripts/generate_ddl.py` whenever a model changes.

Total tables on `Base.metadata`: **34**.

Schema highlights to be aware of:

- **`users`** has no `admin` boolean column — superuser status comes from membership in the seeded `admin` role (doc 21B).
- **`milestones.depends`** JSON column was dropped (doc 22). Milestone deps now live in the `milestone_dependencies` edge table (doc 21A).
- **`subtasks.parent_subtask_id`** (nullable self-FK) supports nested subtasks (doc 24). Top-level subtasks have it NULL; the column always carries the immediate parent.
- **Position uniqueness** for live siblings is enforced by partial-unique indexes on every M/A/T/S level (doc 22, plus doc 24's split for nested subtasks). The label-resolution layer relies on this.
- **`permissions`, `role_permissions`, `user_roles`, `user_permissions`** drive DB-RBAC (doc 21B). The legacy `roles.permissions` JSON column was dropped.

---

## 4. API Endpoint Reference

### System

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | No | Root — API links |
| GET | `/health` | No | Health check |
| GET | `/docs` | No | Swagger UI |
| GET | `/redoc` | No | ReDoc |
| GET | `/openapi.json` | No | OpenAPI document |

### Authentication & users

| Method | Path | Permission | Description |
|--------|------|-----------|-------------|
| POST | `/api/v3/users/login` | Public | Get access + refresh JWT |
| POST | `/api/v3/users/refresh` | Public (refresh-token) | Rotate access token (grace window — doc 19) |
| POST | `/api/v3/users/introspect` | Public | RFC 7662 introspect; resolves `isAdmin` from DB at call time |
| POST | `/api/v3/users/logout` | Authenticated | Revoke current access JTI + clear all refresh slots |
| GET | `/api/v3/users/me` | Authenticated | Current user record |
| GET | `/api/v3/users/me/permissions` | Authenticated | Effective permission set (FE uses to draw UI) |
| POST | `/api/v3/users/create` | `users:create` | Create user (vendor + project mapping required) |
| GET | `/api/v3/users` | `users:read_all` | List users |
| GET | `/api/v3/users/{id}` | `users:read` | Get user |
| PATCH | `/api/v3/users/{id}` | `users:update` (self) / `users:update_all` | Update user |
| PATCH | `/api/v3/users/{id}/password` | `users:update` | Update password |
| DELETE | `/api/v3/users/{id}` | `users:delete_all` | Soft-delete (last-admin protected) |
| POST | `/api/v3/users/{id}/restore` | `users:delete_all` | Restore soft-deleted user |

### RBAC user-side (doc 21B)

| Method | Path | Permission | Description |
|--------|------|-----------|-------------|
| GET | `/api/v3/users/{id}/permissions` | `permissions:read` | Effective permissions for a user |
| POST | `/api/v3/users/{id}/permissions/{code}` | `rbac:assign` | Direct grant (additive) |
| DELETE | `/api/v3/users/{id}/permissions/{code}` | `rbac:assign` | Revoke direct grant |
| GET | `/api/v3/users/{id}/roles` | `permissions:read` | List user's roles |
| POST | `/api/v3/users/{id}/roles/{role_id}` | `rbac:assign` | Assign role |
| DELETE | `/api/v3/users/{id}/roles/{role_id}` | `rbac:assign` | Unassign role (last-admin lockout protected) |

### Projects + versions

| Method | Path | Permission | Description |
|--------|------|-----------|-------------|
| POST | `/api/v3/projects/create` | `projects:create` | Create project (`startDate` may be in past — doc 24) |
| PUT | `/api/v3/projects/{uuid}` | `projects:create`/`projects:update_all` | Idempotent upsert |
| GET | `/api/v3/projects` | `projects:read` | List live projects (paged) |
| GET | `/api/v3/projects/all` | `projects:read_all` | Admin view incl. soft-deleted |
| GET | `/api/v3/projects/{id}` | `projects:read` | Get project |
| PATCH | `/api/v3/projects/{id}` | `projects:update_all` | Update project |
| DELETE | `/api/v3/projects/{id}` | `projects:delete_all` | Soft-delete (cascades to active versions) |
| POST | `/api/v3/projects/{id}/save` | `projects:update_all` | Move `new` → `draft` |
| POST | `/api/v3/projects/{id}/publish` | `projects:publish` | Move `draft` → `published` |
| POST | `/api/v3/projects/{id}/close` | `projects:close` | Move to `closed` |
| POST | `/api/v3/projects/{id}/versions/create` | `projects:update_all` | Create a new version (active-version constraint) |
| GET | `/api/v3/projects/{id}/tree` | `projects:read` | Full nested tree (M/A/T/S, recursive subtask nesting) |

### Master data (`/api/v3/master/*` — doc 20 + 21B follow-up)

| Method | Path | Permission | Description |
|--------|------|-----------|-------------|
| GET | `/api/v3/master/divisions` | `master_data:view` | List divisions |
| POST | `/api/v3/master/divisions/create` | `master_data:manage` | Add division |
| PATCH | `/api/v3/master/divisions/{code}` | `master_data:manage` | Edit division |
| DELETE | `/api/v3/master/divisions/{code}` | `master_data:manage` | Soft-delete (built-ins protected) |
| POST | `/api/v3/master/divisions/{code}/restore` | `master_data:manage` | Restore |
| GET | `/api/v3/master/project_status_transitions` | `master_data:view` | List transitions |
| POST/PATCH/DELETE | `/api/v3/master/project_status_transitions[/…]` | `master_data:manage` | Transition CRUD |
| GET | `/api/v3/master/resource_types` | `master_data:view` | List resource types |
| POST/PATCH/DELETE | `/api/v3/master/resource_types[/…]` | `master_data:manage` | Resource-type CRUD |
| GET | `/api/v3/master/vendors` | `master_data:view` | List vendors |
| POST/PATCH/DELETE | `/api/v3/master/vendors[/…]` | `master_data:manage` | Vendor CRUD (delegates to legacy handlers) |
| GET | `/api/v3/master/roles` | `master_data:view` | List roles (doc 21B follow-up) |
| POST | `/api/v3/master/roles/create` | `master_data:manage` | Create role |
| PATCH/DELETE | `/api/v3/master/roles/{id}` | `master_data:manage` | Edit / delete role (admin role protected) |
| GET | `/api/v3/master/roles/{id}/permissions` | `master_data:view` | List role's permission set |
| PUT | `/api/v3/master/roles/{id}/permissions` | `master_data:manage` | Replace permission set |
| POST/DELETE | `/api/v3/master/roles/{id}/permissions/{code}` | `master_data:manage` | Grant / revoke single |
| GET | `/api/v3/master/permissions` | `master_data:view` | List permission catalog |
| POST | `/api/v3/master/permissions/create` | `master_data:manage` | Create custom permission |
| PATCH/DELETE | `/api/v3/master/permissions/{code}` | `master_data:manage` | Edit / delete (built-ins protected) |

The legacy paths (`/api/v3/divisions`, `/api/v3/resource_types`, `/api/v3/vendors/*`, `/api/v3/roles/*`, `/api/v3/permissions/*`) keep responding but stamp `Deprecation: true` + `Link: <successor>; rel="successor-version"`.

### Milestones / Activities / Tasks / Subtasks

`dependsOn` arrays accept either UUIDs or **display labels** (`M1`, `A1.2`, `T1.2.3`, `S1.2.3.4`, and now `S1.2.3.4.5…` for nested subtasks per doc 24). Every response includes `displayCode` + `dependsOnDisplay`.

**Milestones**
| Method | Path | Permission | Description |
|---|---|---|---|
| POST | `/api/v3/projects/{id}/milestones/create` | `milestones:create` | Create (baseline only). `dependsOn` accepted (doc 21A) |
| GET | `/api/v3/projects/{id}/milestones` | `milestones:read` | List |
| GET | `/api/v3/milestones/{id}` | `milestones:read` | Get |
| PATCH | `/api/v3/milestones/{id}` | `milestones:update` | Update (baseline only) |
| DELETE | `/api/v3/milestones/{id}` | `milestones:delete` | Soft-delete + cascade |
| POST | `/api/v3/milestones/{id}/restore` | `milestones:restore` | Restore |

**Activities** — `POST /milestones/{id}/activities/standard/create` (or `…/resource/create`), `GET/PATCH/DELETE/restore` on `/activities/{id}`. Same dependency rules as milestones; baseline-only writes.

**Tasks** — version-only. `POST /activities/{id}/tasks/create` (type derived from parent activity); `GET/PATCH/DELETE/restore` on `/tasks/{id}`. **Doc 24 part 3: no parent-activity hierarchy rule on dependencies.**

**Subtasks** — version-only.
| Method | Path | Permission | Description |
|---|---|---|---|
| POST | `/api/v3/tasks/{task_id}/subtasks/create` | `subtasks:create` | Top-level subtask under task |
| POST | `/api/v3/subtasks/{parent_subtask_id}/subtasks/create` | `subtasks:create` | **Nested subtask (doc 24)** |
| GET | `/api/v3/tasks/{task_id}/subtasks` | `subtasks:read` | List top-level under task |
| GET | `/api/v3/subtasks/{id}` | `subtasks:read` | Get (response includes `parentSubtaskId`) |
| PATCH/DELETE/restore | `/api/v3/subtasks/{id}` | `subtasks:update`/`delete`/`restore` | Mutate / cascade-soft-delete entire subtree |

**Doc 24 part 3: no parent-task hierarchy rule on dependencies.** Subtask deps follow the same rule as activity deps: same project, no self, no cycle. Cap nesting depth via env var `SUBTASK_MAX_NESTING_DEPTH` (default `None` = unlimited).

### Comments + attachments

Polymorphic on M/A/T/S target — see the route files for the full surface.

---

## 5. Response Format (HAL+JSON)

### Single resource

```json
{
  "data": {
    "_type": "User",
    "_links": { "self": { "href": "/api/v3/users/1", "title": "admin" } },
    "id": 1,
    "login": "admin",
    "firstName": "Admin",
    "lastName": "User",
    "email": "admin@example.com",
    "phoneNumber": "9876543210",
    "admin": true,
    "status": "active",
    "vendor": { "id": "…", "name": "Vendor A" },
    "division": "tmd1",
    "divisionOther": null,
    "projects": [ { "id": "…", "projectCode": "PR-…", "name": "…", "status": "draft" } ],
    "createdAt": "2026-05-01T10:00:00",
    "updatedAt": "2026-05-04T08:30:00"
  },
  "status": 200
}
```

### Collection

```json
{
  "data": {
    "_type": "Collection",
    "_links": { "self": { "href": "/api/v3/users?offset=1&pageSize=20" } },
    "total": 137,
    "count": 20,
    "pageSize": 20,
    "offset": 1,
    "_embedded": { "elements": [ /* … */ ] }
  },
  "status": 200
}
```

### Error

```json
{
  "error": {
    "_type": "Error",
    "errorIdentifier": "not_found",
    "message": "User with ID 99 not found"
  },
  "status": 404
}
```

### Status code taxonomy

| Status | Usage |
|---|---|
| 200 | Successful GET / PATCH / soft-delete on master rows |
| 201 | Successful POST (create) |
| 204 | Successful DELETE returning no body |
| 400 | Bad request |
| 401 | Unauthorized (no token / revoked / decode failure) |
| 403 | Forbidden (lacks permission, last-admin lockout, admin-role lock) |
| 404 | Not found |
| 409 | Conflict (duplicate, active-version exists, etc.) |
| 422 | Validation error |
| 500 | Server error |

---

## 6. RBAC (DB-driven, doc 21B)

### Model

- **Permissions** are string codes (`projects:create`, `master_data:manage`, `rbac:assign`, …). The full registry lives in [app/core/permissions.py](../app/core/permissions.py).
- **Roles** are arbitrary named bundles of permission codes. Three are seeded on startup:
  - **`admin`** — holds every registered permission. Cannot be deleted, renamed, or have its permission set modified. Auto-syncs to include any new permission codes added in code.
  - **`member`** — default contributor set (read/write on M/A/T/S, read on master, etc.).
  - **`viewer`** — read-only.
- **Users** are assigned roles via the `user_roles` table. Effective permissions = union of role-derived ∪ direct grants from `user_permissions`. Direct grants are additive; there is no deny semantics.

### Enforcement

```python
from app.core.middleware.rbac import require_permission
from app.core.permissions import PROJECTS_CREATE

@router.post(
    "/create",
    dependencies=[require_permission(PROJECTS_CREATE)],
    status_code=201,
)
def create_project(...):
    ...
```

Per-request flow: auth middleware loads the user's effective permission set into `request.state.user_permissions` once. The decorator does a `O(1)` set membership check.

### Lockout protections

- Removing the last user holding the `admin` role → 403.
- Deleting / renaming / mutating the `admin` role → 403.
- Self-delete / self-demote on a sole admin → 422.

### JWT contents (doc 21B)

```json
{ "sub": "admin", "user_id": 1, "email": "admin@…", "jti": "…", "iat": …, "exp": … }
```

No `role` / `is_admin` claims — they're resolved from the DB on every request. Tokens issued before doc 21B that still carry those claims keep working; the middleware ignores them.

---

## 7. Configuration

### Environment variables

```bash
SECRET_KEY=<32+ char secure key>
DATABASE_URL=sqlite:///./pmis.db                    # or postgresql://user:pw@host/db
DEBUG=False
CORS_ORIGINS=["http://localhost:3000"]
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
REFRESH_TOKEN_GRACE_SECONDS=120                     # doc 19
DEFAULT_PAGE_SIZE=20
MAX_PAGE_SIZE=100
BOOTSTRAP_ADMIN_LOGIN=admin
BOOTSTRAP_ADMIN_EMAIL=admin@example.com
BOOTSTRAP_ADMIN_PASSWORD=admin123
SUBTASK_MAX_NESTING_DEPTH=                          # doc 24 — None = unlimited
```

### Bootstrap admin

On first boot the RBAC seed creates the `admin` role (and its permissions) and assigns it to the bootstrap user. The bootstrap user can be deleted later as long as another user holds the `admin` role (lockout guard). Defaults: `admin` / `admin123`.

### Running

```bash
# Dev
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Prod
gunicorn -w 4 -b 0.0.0.0:8000 --worker-class uvicorn.workers.UvicornWorker app.main:app
```

### API documentation

- Swagger UI: `http://<host>:8000/docs`
- ReDoc: `http://<host>:8000/redoc`
- OpenAPI JSON: `http://<host>:8000/openapi.json`

---

## 8. Migration history (planned_changes/)

Numbered docs in [planned_changes/](../planned_changes/) describe every BE shape change with reasoning. Most relevant since 19:

| Doc | Topic |
|---|---|
| 19 | Refresh-token grace window |
| 20 | `/api/v3/master/*` consolidation; project_owners removed |
| 21A | Milestone-to-milestone dependencies |
| 21B | DB-driven RBAC overhaul |
| 21B follow-up | Roles + permissions CRUD relocated under `/master/*` |
| 22 | Display labels (M/A/T/S) + drop `milestones.depends` JSON + per-parent position uniqueness |
| 23 | Users `phone_number` + vendor `phoneNumber` required |
| 24 | Past `start_date`, nested subtasks, drop dependency hierarchy rules |
